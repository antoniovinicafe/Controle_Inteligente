class Recorrencia {
  final int id;
  final int turmaId;
  final String titulo;
  final String? descricao;
  final String? local;
  /// ISO: 1 = segunda .. 7 = domingo.
  final List<int> diasSemana;
  final String horaInicio; // "HH:MM:SS" como vem do Postgres
  final String horaFim;
  final DateTime dataInicio;
  final DateTime dataFim;
  final int? capacidade;

  Recorrencia({
    required this.id,
    required this.turmaId,
    required this.titulo,
    required this.descricao,
    required this.local,
    required this.diasSemana,
    required this.horaInicio,
    required this.horaFim,
    required this.dataInicio,
    required this.dataFim,
    required this.capacidade,
  });

  factory Recorrencia.fromJson(Map<String, dynamic> json) {
    return Recorrencia(
      id: json['id'] as int,
      turmaId: json['turma_id'] as int,
      titulo: json['titulo'] as String,
      descricao: json['descricao'] as String?,
      local: json['local'] as String?,
      diasSemana: (json['dias_semana'] as List).map((e) => e as int).toList(),
      horaInicio: json['hora_inicio'] as String,
      horaFim: json['hora_fim'] as String,
      dataInicio: DateTime.parse(json['data_inicio'] as String),
      dataFim: DateTime.parse(json['data_fim'] as String),
      capacidade: (json['capacidade'] as num?)?.toInt(),
    );
  }
}

/// Chaves são o mesmo 1-7 de `DateTime.weekday` no Dart e de `isoweekday()`
/// no Python - é o que deixa [contarOcorrencias] bater com o backend.
const nomesDiasSemana = {
  1: 'Seg',
  2: 'Ter',
  3: 'Qua',
  4: 'Qui',
  5: 'Sex',
  6: 'Sáb',
  7: 'Dom',
};

/// Quantas aulas uma regra de recorrência vai gerar.
///
/// Reproduz de propósito a varredura dia-a-dia de `routes/recorrencias.py`,
/// que percorre o intervalo comparando `isoweekday()` com `dias_semana`.
/// Serve pra dizer o número ANTES de criar - a criação é em lote e desfazer
/// é de um em um.
///
/// Está aqui fora (e não dentro da tela) pra poder ser testada: se um dia
/// as duas contas discordarem, o app promete uma coisa e o servidor faz
/// outra, que é pior do que não prometer nada.
int contarOcorrencias(Set<int> diasSemana, DateTime inicio, DateTime fim) {
  if (diasSemana.isEmpty) return 0;

  // Normaliza pra meia-noite: hora sobrando faria o último dia do intervalo
  // ficar de fora quando `fim` tem hora menor que `inicio`.
  var dia = DateTime(inicio.year, inicio.month, inicio.day);
  final ultimo = DateTime(fim.year, fim.month, fim.day);
  if (ultimo.isBefore(dia)) return 0;

  var total = 0;
  while (!dia.isAfter(ultimo)) {
    if (diasSemana.contains(dia.weekday)) total++;
    // Somar 1 dia em Duration atravessa horário de verão somando 23h ou 25h
    // e pode repetir/pular uma data. Construir a próxima data explicitamente
    // evita isso (o DateTime normaliza dia 32 pro mês seguinte sozinho).
    dia = DateTime(dia.year, dia.month, dia.day + 1);
  }
  return total;
}
