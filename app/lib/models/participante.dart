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

  /// Primeira e última vez que a porta liberou essa pessoa nesta aula.
  ///
  /// NÃO é entrada e saída: o sistema sabe quando VIU, não quando a pessoa
  /// foi embora. Quem entra e não passa mais na frente da câmera tem uma
  /// leitura só. Por isso a tela diz "visto por último" e não "saiu".
  final DateTime? primeiraLeitura;
  final DateTime? ultimaLeitura;
  final int leituras;

  Participante({
    required this.id,
    required this.status,
    required this.origem,
    required this.liberadoEm,
    required this.usuarioId,
    required this.nome,
    required this.matricula,
    required this.temRosto,
    this.primeiraLeitura,
    this.ultimaLeitura,
    this.leituras = 0,
  });

  bool get liberado => status == 'liberado';

  /// Foi visto mais de uma vez, em momentos diferentes: dá pra dizer por
  /// quanto tempo esteve por perto. Com uma leitura só, não dá.
  bool get temPermanencia =>
      leituras > 1 &&
      primeiraLeitura != null &&
      ultimaLeitura != null &&
      ultimaLeitura!.difference(primeiraLeitura!).inMinutes >= 1;

  Duration? get permanencia =>
      temPermanencia ? ultimaLeitura!.difference(primeiraLeitura!) : null;

  static DateTime? _data(dynamic v) =>
      v is String ? DateTime.parse(v).toLocal() : null;

  factory Participante.fromJson(Map<String, dynamic> json) => Participante(
        id: json['id'] as int,
        status: json['status'] as String,
        origem: json['origem'] as String,
        liberadoEm: _data(json['liberado_em']),
        usuarioId: json['usuario_id'] as String,
        nome: json['nome'] as String,
        matricula: json['matricula'] as String?,
        temRosto: json['tem_rosto'] as bool? ?? false,
        primeiraLeitura: _data(json['primeira_leitura']),
        ultimaLeitura: _data(json['ultima_leitura']),
        leituras: (json['leituras'] as num?)?.toInt() ?? 0,
      );
}
