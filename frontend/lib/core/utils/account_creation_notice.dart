/// Builds a safe account-creation notice from the backend email provider status.
///
/// `accepted` means the provider accepted the message; it does not guarantee
/// delivery to the recipient's inbox. Unknown or absent values remain
/// conservative for compatibility with older backend responses.
String accountCreationNotice({
  required String accountType,
  required Object? emailDeliveryStatus,
}) {
  final status = emailDeliveryStatus is String
      ? emailDeliveryStatus.toLowerCase()
      : null;

  return switch (status) {
    'accepted' =>
      '$accountType creado. El proveedor aceptó el correo; la llegada a la bandeja no está confirmada.',
    'disabled' =>
      '$accountType creado, pero el envío de correo está deshabilitado. Solicita ayuda para habilitar el acceso; no vuelvas a crear la cuenta.',
    'failed' =>
      '$accountType creado, pero el proveedor no confirmó el envío. Solicita ayuda para habilitar el acceso; no vuelvas a crear la cuenta.',
    _ =>
      '$accountType creado, pero no se pudo confirmar el estado del correo. Verifica el acceso; no vuelvas a crear la cuenta.',
  };
}
