class Perfil {
  final String id;
  final String nome;
  final String? matricula;
  final String role; // 'admin' | 'professor' | 'aluno'

  Perfil({
    required this.id,
    required this.nome,
    required this.matricula,
    required this.role,
  });

  bool get isProfessor => role == 'professor' || role == 'admin';
  bool get isAluno => role == 'aluno';

  factory Perfil.fromJson(Map<String, dynamic> json) {
    return Perfil(
      id: json['id'] as String,
      nome: json['nome'] as String,
      matricula: json['matricula'] as String?,
      role: json['role'] as String,
    );
  }
}
