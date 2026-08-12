class AccessLog {
  final int id;
  final String tipo; // facial | manual
  final String status; // liberado | negado
  final String? dispositivo; // ex: 'raspberry-sala-201'
  final DateTime criadoEm;

  /// Por que liberou ou negou. Só "negado" não diz o que fazer: "rosto
  /// não reconhecido" pede liberação manual, "não está na lista" pede o
  /// contrário. Null nos logs antigos, gravados antes desse campo existir.
  final String? motivo;

  /// Vêm do join com profiles - null quando o rosto não foi reconhecido.
  final String? nome;
  final String? matricula;

  AccessLog({
    required this.id,
    required this.tipo,
    required this.status,
    required this.dispositivo,
    required this.criadoEm,
    required this.motivo,
    required this.nome,
    required this.matricula,
  });

  bool get liberado => status == 'liberado';
  bool get porReconhecimento => tipo == 'facial';

  factory AccessLog.fromJson(Map<String, dynamic> json) {
    return AccessLog(
      id: json['id'] as int,
      tipo: json['tipo'] as String,
      status: json['status'] as String,
      dispositivo: json['dispositivo'] as String?,
      criadoEm: DateTime.parse(json['criado_em'] as String).toLocal(),
      motivo: json['motivo'] as String?,
      nome: json['nome'] as String?,
      matricula: json['matricula'] as String?,
    );
  }
}
