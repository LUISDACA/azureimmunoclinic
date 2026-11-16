/// Retains notification taps until the authenticated router can handle them.
class NotificationTapCoordinator {
  NotificationTapCoordinator();

  static final NotificationTapCoordinator instance =
      NotificationTapCoordinator();

  bool _pendingOpen = false;
  bool Function()? _handler;

  bool get hasPendingOpen => _pendingOpen;

  /// Installs the app-level navigation handler and retries a tap received
  /// before the router or authenticated session was ready.
  void setHandler(bool Function() handler) {
    _handler = handler;
    retry();
  }

  void requestOpen() {
    _pendingOpen = true;
    retry();
  }

  /// Returns true only when the pending navigation was accepted.
  void retry() {
    if (!_pendingOpen) return;
    final handler = _handler;
    if (handler != null && handler()) _pendingOpen = false;
  }
}
