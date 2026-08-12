class Participante {
  final int id;
  final String status; // convidado | liberado | negado
  final String origem; // turma | manual
  final DateTime? liberadoEm;
  final String usuarioId;
  final String nome;
  final String? matricula;

  /// Sem rosto cadastrado o reconhecimento facial nunca vai liberar essa
  /// pessoa - ela sempre vai depender de liberação manual do professor.
  final bool temRosto;

  Participante({
    required this.id,
    required this.status,
    required this.origem,
    required this.liberadoEm,
    required this.usuarioId,
    required this.nome,
    required this.matricula,
    required this.temRosto,
  });

  bool get liberado => status == 'liberado';

  factory Participante.fromJson(Map<String, dynamic> json) {
    final liberadoEm = json['liberado_em'] as String?;
    return Participante(
      id: json['id'] as int,
      status: json['status'] as String,
      origem: json['origem'] as String,
      liberadoEm:
          liberadoEm != null ? DateTime.parse(liberadoEm).toLocal() : null,
      usuarioId: json['usuario_id'] as String,
      nome: json['nome'] as String,
      matricula: json['matricula'] as String?,
      temRosto: json['tem_rosto'] as bool? ?? false,
    );
  }
}
