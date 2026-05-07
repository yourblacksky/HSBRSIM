using System;
using System.IO;
using System.Timers;
using System.Windows;
using System.Windows.Controls;
using Hearthstone_Deck_Tracker.API;
using Hearthstone_Deck_Tracker.Plugins;
using Hearthstone_Deck_Tracker.Enums;

namespace HrSRLAdviser
{
    public class AdviserPlugin : IPlugin
    {
        public string Name => "HrSRL Adviser";
        public string Description =>
            "AI-powered Battlegrounds action suggestions using a trained " +
            "reinforcement learning model running in a local Python server.";
        public string Author => "HrSRL";
        public Version Version => new Version(1, 0, 0, 0);
        public string ButtonText => "Settings";
        public MenuItem MenuItem => null;

        private WebSocketClient _wsClient;
        private GameStateExtractor _extractor;
        private SuggestionOverlay _overlay;
        private Timer _sendTimer;
        private bool _enabled;
        private string _gameId;
        private bool _inBattlegrounds;
        private bool _gameStartSent;
        private DateTime _lastSendTime = DateTime.MinValue;
        private const int SendIntervalMs = 250;

        public void OnLoad()
        {
            _enabled = true;
            _extractor = new GameStateExtractor();

            _wsClient = new WebSocketClient("ws://127.0.0.1:9777");
            _wsClient.OnSuggestionsReceived += OnSuggestionsReceived;
            _wsClient.OnError += OnError;
            _ = _wsClient.ConnectAsync();

            GameEvents.OnGameStart.Add(OnGameStart);
            GameEvents.OnGameEnd.Add(OnGameEnd);
            GameEvents.OnInMenu.Add(OnInMenu);

            _overlay = new SuggestionOverlay();
            Core.OverlayCanvas.Children.Add(_overlay);

            _sendTimer = new Timer(SendIntervalMs);
            _sendTimer.Elapsed += (s, e) => SendGameStateIfNeeded();
            _sendTimer.AutoReset = true;
            _sendTimer.Start();

            // Handle case where a BG game is already in progress when plugin loads
            CheckExistingGame();

            Log("HrSRL Adviser loaded");
        }

        /// <summary>
        /// Poll-based fallback: detect BG game even if HDT events were missed.
        /// Called periodically by the send timer when _inBattlegrounds is
        /// false.
        /// </summary>
        private void TryDetectBattlegroundsGame()
        {
            var game = Core.Game;
            if (game == null || !game.IsRunning || !game.IsBattlegroundsMatch) return;

            _inBattlegrounds = true;
            _gameId = "bg_" + DateTime.Now.ToString("yyyyMMdd_HHmmss") +
                      "_" + new Random().Next(1000, 9999);
            _gameStartSent = false;
            _lastSendTime = DateTime.MinValue;
            Log("BG game detected via polling: " + _gameId);
        }

        /// <summary>
        /// If a Battlegrounds game is already running when the plugin loads,
        /// initialize game tracking (OnGameStart already fired before we were
        /// loaded).
        /// </summary>
        private void CheckExistingGame()
        {
            var game = Core.Game;
            if (game == null)
            {
                Log("CheckExistingGame: Core.Game is null");
                return;
            }
            if (!game.IsRunning)
            {
                Log("CheckExistingGame: game not running");
                return;
            }
            if (!game.IsBattlegroundsMatch)
            {
                Log("CheckExistingGame: not BG match");
                return;
            }

            _inBattlegrounds = true;
            _gameId = "bg_" + DateTime.Now.ToString("yyyyMMdd_HHmmss") +
                      "_" + new Random().Next(1000, 9999);
            _gameStartSent = false;
            _lastSendTime = DateTime.MinValue;
            Log("Existing BG game detected: " + _gameId);
        }

        public void OnUnload()
        {
            _enabled = false;

            _sendTimer?.Stop();
            _sendTimer?.Dispose();

            // HDT ActionList has no public Remove(); engine auto-skips
            // disabled plugin handlers internally.

            _wsClient?.DisconnectAsync();
            _wsClient = null;

            if (_overlay != null)
            {
                Core.OverlayCanvas.Children.Remove(_overlay);
                _overlay = null;
            }

            Log("HrSRL Adviser unloaded");
        }

        public void OnButtonPress()
        {
            var status = _wsClient?.IsConnected == true ? "Connected" : "Disconnected";
            MessageBox.Show(
                "HrSRL Adviser v1.0\n\n" +
                "Make sure the Python inference server is running:\n" +
                "  python -m hsrl.advisor.cli --model <checkpoint.zip>\n\n" +
                "Server: ws://127.0.0.1:9777\n" +
                "Status: " + status,
                "HrSRL Adviser");
        }

        public void OnUpdate() { /* throttled sending handled by timer */ }

        // ── Game events ──────────────────────────────────────────────────

        private void OnGameStart()
        {
            try
            {
                if (!_enabled)
                {
                    Log("OnGameStart: not enabled");
                    return;
                }
                var game = Core.Game;
                if (game == null)
                {
                    Log("OnGameStart: Core.Game is null");
                    return;
                }
                if (!game.IsRunning)
                {
                    Log("OnGameStart: game not running");
                    return;
                }
                // Don't check GameMode here — it's often still None when this
                // event fires. The polling method will verify BG mode when
                // sending game states.

                _inBattlegrounds = true;
                _gameId = "bg_" + DateTime.Now.ToString("yyyyMMdd_HHmmss") +
                          "_" + new Random().Next(1000, 9999);
                _gameStartSent = false;
                _lastSendTime = DateTime.MinValue;
                Log("Game started: " + _gameId);
            }
            catch (Exception ex)
            {
                Log("OnGameStart ERROR: " + ex.Message);
            }
        }

        private void OnGameEnd()
        {
            if (!_enabled || !_inBattlegrounds) return;

            var placement = _extractor.GetPlacement();
            _wsClient?.SendAsync(new
            {
                type = "game_end",
                game_id = _gameId,
                placement = placement,
                mmr_change = 0
            });

            _overlay?.Clear();
            Log("Game ended: " + _gameId + " placement=" + placement);

            _inBattlegrounds = false;
            _gameId = null;
        }

        private void OnInMenu()
        {
            if (_inBattlegrounds && _gameId != null)
                OnGameEnd();
        }

        // ── State sending ────────────────────────────────────────────────

        private void SendGameStateIfNeeded()
        {
            if (!_enabled)
            {
                Log("SendGameStateIfNeeded: not enabled");
                return;
            }
            if (!_inBattlegrounds)
            {
                // Poll for BG game in case events were missed
                TryDetectBattlegroundsGame();
                if (!_inBattlegrounds) return;
            }
            if (_gameId == null) return;
            if (_wsClient == null) return;
            if (!_wsClient.IsConnected)
            {
                return; // WS not connected yet, silent
            }

            // Send game_start on first opportunity (WebSocket is now connected)
            if (!_gameStartSent)
            {
                var heroCardId = "";
                var game = Core.Game;
                if (game != null && game.Entities.TryGetValue(
                    game.Player.Id, out var playerEntity))
                    heroCardId = playerEntity.CardId ?? "";

                Log("Sending game_start: gameId=" + _gameId);
                _wsClient.SendAsync(new
                {
                    type = "game_start",
                    game_id = _gameId,
                    hero_card_id = heroCardId,
                    mmr = 0,
                    timestamp = DateTime.Now.ToString("O")
                });
                _gameStartSent = true;
            }

            if ((DateTime.Now - _lastSendTime).TotalMilliseconds < SendIntervalMs) return;

            var state = _extractor.Extract(_gameId);
            if (state == null) return;
            if (state.phase != "recruit") return;

            _lastSendTime = DateTime.Now;
            _wsClient.SendAsync(state);
        }

        // ── Response handlers ────────────────────────────────────────────

        private void OnSuggestionsReceived(SuggestionsMessage suggestions)
        {
            if (!_enabled) return;
            Application.Current?.Dispatcher.Invoke(() =>
                _overlay?.UpdateSuggestions(suggestions));
        }

        private void OnError(string message)
        {
            Log("Error: " + message);
            Application.Current?.Dispatcher.Invoke(() =>
                _overlay?.ShowError(message));
        }

        // ── Logging ──────────────────────────────────────────────────────

        private static readonly string LogPath =
            Path.Combine(Environment.GetFolderPath(
                Environment.SpecialFolder.LocalApplicationData),
                "HearthstoneDeckTracker", "hrsrl_adviser.log");

        internal static void Log(string msg)
        {
            var line = DateTime.Now.ToString("HH:mm:ss.fff") + " " + msg;
            System.Diagnostics.Debug.WriteLine("[HrSRL] " + line);
            try { File.AppendAllText(LogPath, line + Environment.NewLine); }
            catch { }
        }
    }
}
