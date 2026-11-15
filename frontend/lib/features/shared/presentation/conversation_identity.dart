String conversationRoleLabel(Map<String, dynamic> user) {
  switch (user['role']?.toString()) {
    case 'student':
      return 'Estudiante';
    case 'app_admin':
      return 'Administrador de aplicación';
    case 'admin':
      final jobTitle = user['job_title']?.toString().trim() ?? '';
      return jobTitle.isEmpty ? 'Administrador' : jobTitle;
    default:
      return 'Usuario';
  }
}

String conversationIdentity(Map<String, dynamic>? user) {
  if (user == null) return 'Usuario';
  final name = user['name']?.toString().trim() ?? '';
  final role = conversationRoleLabel(user);
  if (name.isNotEmpty) return '$name · $role';
  final email = user['email']?.toString().trim() ?? '';
  return email.isEmpty ? role : '$role · $email';
}
