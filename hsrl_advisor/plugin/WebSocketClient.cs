using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace HrSRLAdviser
{
    /// <summary>
    /// WebSocket client for communicating with the HrSRL Python inference server.
    /// Uses System.Net.WebSockets with JSON serialization via Newtonsoft.
    /// Auto-reconnects with exponential backoff.
    /// </summary>
    public class WebSocketClient
    {
        private readonly string _url;
        private System.Net.WebSockets.ClientWebSocket _ws;
        private CancellationTokenSource _cts;
        private bool _running;
        private int _reconnectAttempts;
        private const int MaxReconnectDelayMs = 30000;
        private const int InitialReconnectDelayMs = 1000;

        public bool IsConnected => _ws?.State == System.Net.WebSockets.WebSocketState.Open;

        public event Action<SuggestionsMessage> OnSuggestionsReceived;
        public event Action<string> OnError;

        public WebSocketClient(string url)
        {
            _url = url;
        }

        public async Task ConnectAsync()
        {
            _running = true;
            _cts = new CancellationTokenSource();
            _ = Task.Run(ConnectLoopAsync);
        }

        public async Task DisconnectAsync()
        {
            _running = false;
            _cts?.Cancel();

            if (_ws != null && _ws.State == System.Net.WebSockets.WebSocketState.Open)
            {
                try
                {
                    await _ws.CloseAsync(
                        System.Net.WebSockets.WebSocketCloseStatus.NormalClosure,
                        "Plugin closing", CancellationToken.None);
                }
                catch { }
            }

            _ws?.Dispose();
            _ws = null;
        }

        public async Task SendAsync(object message)
        {
            if (_ws?.State != System.Net.WebSockets.WebSocketState.Open) return;

            try
            {
                var settings = new JsonSerializerSettings
                {
                    NullValueHandling = NullValueHandling.Ignore,
                };
                var json = JsonConvert.SerializeObject(message, settings);
                var bytes = System.Text.Encoding.UTF8.GetBytes(json);

                await _ws.SendAsync(
                    new ArraySegment<byte>(bytes),
                    System.Net.WebSockets.WebSocketMessageType.Text,
                    endOfMessage: true,
                    _cts.Token);
            }
            catch (Exception ex)
            {
                OnError?.Invoke("Send failed: " + ex.Message);
            }
        }

        // ── Internal ────────────────────────────────────────────────────

        private async Task ConnectLoopAsync()
        {
            while (_running)
            {
                try
                {
                    _ws?.Dispose();
                    _ws = new System.Net.WebSockets.ClientWebSocket();

                    using (var timeoutCts = new CancellationTokenSource(5000))
                    using (var linked = CancellationTokenSource.CreateLinkedTokenSource(
                        timeoutCts.Token, _cts.Token))
                    {
                        await _ws.ConnectAsync(new Uri(_url), linked.Token);
                    }

                    _reconnectAttempts = 0;
                    AdviserPlugin.Log("WebSocket connected to " + _url);

                    await ReceiveLoopAsync();
                }
                catch (OperationCanceledException)
                {
                    break;
                }
                catch (Exception ex)
                {
                    _reconnectAttempts++;
                    var delay = Math.Min(
                        InitialReconnectDelayMs * (int)Math.Pow(2, _reconnectAttempts - 1),
                        MaxReconnectDelayMs);

                    AdviserPlugin.Log(
                        "Connection attempt " + _reconnectAttempts +
                        " failed: " + ex.Message +
                        " (retry in " + delay + "ms)");

                    try { await Task.Delay(delay, _cts.Token); }
                    catch (OperationCanceledException) { break; }
                }
            }
        }

        private async Task ReceiveLoopAsync()
        {
            var buffer = new byte[8192];

            while (_ws.State == System.Net.WebSockets.WebSocketState.Open &&
                   !_cts.IsCancellationRequested)
            {
                var result = await _ws.ReceiveAsync(
                    new ArraySegment<byte>(buffer), _cts.Token);

                if (result.MessageType == System.Net.WebSockets.WebSocketMessageType.Close)
                {
                    await _ws.CloseAsync(
                        System.Net.WebSockets.WebSocketCloseStatus.NormalClosure,
                        "", CancellationToken.None);
                    break;
                }

                if (result.MessageType == System.Net.WebSockets.WebSocketMessageType.Text)
                {
                    var json = System.Text.Encoding.UTF8.GetString(buffer, 0, result.Count);
                    ProcessMessage(json);
                }
            }
        }

        private void ProcessMessage(string json)
        {
            try
            {
                var obj = JObject.Parse(json);
                var type = (string)obj["type"];

                if (type == "suggestions")
                {
                    var suggestions = JsonConvert.DeserializeObject<SuggestionsMessage>(json);
                    OnSuggestionsReceived?.Invoke(suggestions);
                }
                else if (type == "error")
                {
                    var message = (string)obj["message"] ?? "Unknown error";
                    OnError?.Invoke(message);
                }
            }
            catch (Exception ex)
            {
                AdviserPlugin.Log("Failed to parse message: " + ex.Message);
            }
        }
    }
}
