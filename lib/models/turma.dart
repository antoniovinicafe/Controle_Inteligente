class Turma {
  final int id;
  final String nome;
  final String professorId;

  /// Só vem quando quem lista é professor/admin (o backend faz o count).
  final int? totalAlunos;

  Turma({
    required this.id,
    required this.nome,
    required this.professorId,
    this.totalAlunos,
  });

  factory Turma.fromJson(Map<String, dynamic> json) {
    return Turma(
      id: json['id'] as int,
      nome: json['nome'] as String,
      professorId: json['professor_id'] as String,
      totalAlunos: (json['total_alunos'] as num?)?.toInt(),
    );
  }
}
