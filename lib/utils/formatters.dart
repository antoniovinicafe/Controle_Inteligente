// Formatação de data/hora sem depender do pacote `intl` (que exigiria
// inicializar locale). O app é pt-BR only, então dd/MM resolve.

String _doisDigitos(int n) => n.toString().padLeft(2, '0');

String formatarData(DateTime d) =>
    '${_doisDigitos(d.day)}/${_doisDigitos(d.month)}/${d.year}';

String formatarHora(DateTime d) =>
    '${_doisDigitos(d.hour)}:${_doisDigitos(d.minute)}';

String formatarDataHora(DateTime d) => '${formatarData(d)} às ${formatarHora(d)}';

/// "10/08 · 18:02–19:32" - versão enxuta pra lista.
///
/// A longa ("10/08/2026 às 18:02 - 19:32") não cabe numa linha quando o
/// texto é monoespaçado, e quebrar em duas fazia a data competir com o
/// título do evento. O ano só aparece quando não é o ano corrente, que é
/// quando ele realmente informa alguma coisa.
String formatarPeriodoCurto(DateTime inicio, DateTime fim) {
  final ano = inicio.year != DateTime.now().year ? '/${inicio.year}' : '';
  final dia = '${_doisDigitos(inicio.day)}/${_doisDigitos(inicio.month)}$ano';

  final mesmoDia = inicio.year == fim.year &&
      inicio.month == fim.month &&
      inicio.day == fim.day;
  if (mesmoDia) {
    return '$dia · ${formatarHora(inicio)}–${formatarHora(fim)}';
  }
  return '$dia ${formatarHora(inicio)} → '
      '${_doisDigitos(fim.day)}/${_doisDigitos(fim.month)} ${formatarHora(fim)}';
}

/// "42 min", "1h 10min", "4 dias" - para contagem regressiva na tela Agora.
///
/// A partir de um dia a contagem passa a ser em dias: "97h 1min" está certo
/// e não serve pra nada, porque ninguém converte 97 horas de cabeça. Os
/// minutos também somem aí - quem olha uma aula de daqui a quatro dias não
/// se importa com o minuto exato.
String formatarDuracaoCurta(Duration d) {
  if (d.inMinutes < 1) return 'menos de 1 min';
  if (d.inMinutes < 60) return '${d.inMinutes} min';

  if (d.inHours >= 24) {
    // Arredonda pra cima: faltando 1 dia e 20 horas, "2 dias" descreve
    // melhor a espera do que "1 dia".
    final dias = (d.inHours / 24).round();
    if (dias == 1) return '1 dia';
    return '$dias dias';
  }

  final horas = d.inHours;
  final minutos = d.inMinutes % 60;
  return minutos == 0 ? '${horas}h' : '${horas}h ${minutos}min';
}

/// "12/03/2026 às 14:00 - 16:00" quando começa e termina no mesmo dia,
/// senão mostra as duas datas inteiras.
String formatarPeriodo(DateTime inicio, DateTime fim) {
  final mesmoDia = inicio.year == fim.year &&
      inicio.month == fim.month &&
      inicio.day == fim.day;
  if (mesmoDia) {
    return '${formatarData(inicio)} às ${formatarHora(inicio)} - ${formatarHora(fim)}';
  }
  return '${formatarDataHora(inicio)} até ${formatarDataHora(fim)}';
}
