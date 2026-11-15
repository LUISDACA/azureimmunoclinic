import 'package:flutter_test/flutter_test.dart';
import 'package:immuno_clinic_app/core/utils/account_creation_notice.dart';

void main() {
  test(
    'accepted reports provider acceptance without promising inbox delivery',
    () {
      final message = accountCreationNotice(
        accountType: 'Estudiante',
        emailDeliveryStatus: 'accepted',
      );

      expect(message, contains('El proveedor aceptó el correo'));
      expect(message, contains('la llegada a la bandeja no está confirmada'));
    },
  );

  test('failed and disabled statuses warn against recreating the account', () {
    for (final status in ['failed', 'disabled']) {
      final message = accountCreationNotice(
        accountType: 'Administrador',
        emailDeliveryStatus: status,
      );

      expect(message, contains('no vuelvas a crear la cuenta'));
      expect(message, contains('Solicita ayuda'));
    }
  });

  test('unknown or missing status does not claim the email was sent', () {
    for (final status in [null, 'queued']) {
      final message = accountCreationNotice(
        accountType: 'Estudiante',
        emailDeliveryStatus: status,
      );

      expect(message, contains('no se pudo confirmar el estado del correo'));
      expect(message, contains('no vuelvas a crear la cuenta'));
    }
  });
}
