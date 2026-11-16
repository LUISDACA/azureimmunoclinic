import 'package:flutter_test/flutter_test.dart';
import 'package:immuno_clinic_app/core/notifications/notification_tap_coordinator.dart';

void main() {
  group('NotificationTapCoordinator', () {
    test('keeps a tap until a router handler is installed', () {
      final coordinator = NotificationTapCoordinator();
      var handled = 0;

      coordinator.requestOpen();

      expect(coordinator.hasPendingOpen, isTrue);
      coordinator.setHandler(() {
        handled++;
        return true;
      });

      expect(handled, 1);
      expect(coordinator.hasPendingOpen, isFalse);
    });

    test('retries after authentication becomes ready', () {
      final coordinator = NotificationTapCoordinator();
      var isAuthenticated = false;
      var handled = 0;
      coordinator.setHandler(() {
        if (!isAuthenticated) return false;
        handled++;
        return true;
      });

      coordinator.requestOpen();
      expect(coordinator.hasPendingOpen, isTrue);

      isAuthenticated = true;
      coordinator.retry();

      expect(handled, 1);
      expect(coordinator.hasPendingOpen, isFalse);
    });

    test('coalesces repeated taps while navigation is pending', () {
      final coordinator = NotificationTapCoordinator();
      var canNavigate = false;
      var handled = 0;
      coordinator.setHandler(() {
        if (!canNavigate) return false;
        handled++;
        return true;
      });

      coordinator.requestOpen();
      coordinator.requestOpen();
      canNavigate = true;
      coordinator.retry();

      expect(handled, 1);
      expect(coordinator.hasPendingOpen, isFalse);
    });
  });
}
