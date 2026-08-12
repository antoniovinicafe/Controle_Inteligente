class Evento {
  final int id;
  final String titulo;
  final String? descricao;
  final String? local;
  final String criadorId;
  final DateTime dataInicio;
  final DateTime dataFim;
  final int? capacidade; // null = sem limite
  final String status; // agendado | em_andamento | encerrado | cancelado

  /// Extras que o backend só devolve pra professor/admin na listagem.
  final int? totalParticipantes;
  final int? totalLiberados;

  /// Extra que o backend só devolve pro aluno na listagem
  /// (o status DELE naquele evento: convidado | liberado | negado).
  final String? meuStatus;

  /// null = evento avulso. Não-nulo = veio de uma aula recorrente
  /// (ver models/recorrencia.dart) - a tela de detalhe oferece
  /// "cancelar a série toda" nesse caso.
  final int? recorrenciaId;

  Evento({
    required this.id,
    required this.titulo,
    required this.descricao,
    required this.local,
    required this.criadorId,
    required this.dataInicio,
    required this.dataFim,
    required this.capacidade,
    required this.status,
    this.totalParticipantes,
    this.totalLiberados,
    this.meuStatus,
    this.recorrenciaId,
  });

  bool get emAndamento => status == 'em_andamento';
  bool get cancelado => status == 'cancelado';
  bool get encerrado => status == 'encerrado';

  factory Evento.fromJson(Map<String, dynamic> json) {
    return Evento(
      id: json['id'] as int,
      titulo: json['titulo'] as String,
      descricao: json['descricao'] as String?,
      local: json['local'] as String?,
      criadorId: json['criador_id'] as String,
      dataInicio: DateTime.parse(json['data_inicio'] as String).toLocal(),
      dataFim: DateTime.parse(json['data_fim'] as String).toLocal(),
      capacidade: (json['capacidade'] as num?)?.toInt(),
      status: json['status'] as String,
      totalParticipantes: (json['total_participantes'] as num?)?.toInt(),
      totalLiberados: (json['total_liberados'] as num?)?.toInt(),
      meuStatus: json['meu_status'] as String?,
      recorrenciaId: (json['recorrencia_id'] as num?)?.toInt(),
    );
  }
}
