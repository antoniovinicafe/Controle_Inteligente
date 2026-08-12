import 'package:flutter_test/flutter_test.dart';
import 'package:inatel_access/utils/formatters.dart';

/// A contagem regressiva da tela Agora é a primeira coisa que a pessoa lê
/// ao abrir o app, e é fácil ela ficar tecnicamente certa e inútil - foi
/// exatamente o que apareceu numa captura de tela: "começa em 97h 1min".
void main() {
  group('formatarDuracaoCurta', () {
    test('abaixo de um minuto não mostra zero', () {
      expect(formatarDuracaoCurta(const Duration(seconds: 30)), 'menos de 1 min');
    });

    test('minutos soltos', () {
      expect(formatarDuracaoCurta(const Duration(minutes: 42)), '42 min');
    });

    test('hora cheia não arrasta "0min"', () {
      expect(formatarDuracaoCurta(const Duration(hours: 2)), '2h');
    });

    test('hora quebrada mostra os minutos', () {
      expect(formatarDuracaoCurta(const Duration(hours: 1, minutes: 10)), '1h 10min');
    });

    test('59 minutos ainda são minutos', () {
      expect(formatarDuracaoCurta(const Duration(minutes: 59)), '59 min');
    });

    test('23h59 ainda são horas', () {
      expect(
        formatarDuracaoCurta(const Duration(hours: 23, minutes: 59)),
        '23h 59min',
      );
    });

    test('exatamente 24h vira "1 dia", não "24h"', () {
      expect(formatarDuracaoCurta(const Duration(hours: 24)), '1 dia');
    });

    test('o caso que apareceu na tela: 97h vira "4 dias"', () {
      expect(
        formatarDuracaoCurta(const Duration(hours: 97, minutes: 1)),
        '4 dias',
      );
    });

    test('arredonda pra cima quando passa da metade do dia', () {
      // 1 dia e 20 horas descreve melhor uma espera de "2 dias".
      expect(formatarDuracaoCurta(const Duration(hours: 44)), '2 dias');
    });

    test('não pluraliza "1 dia"', () {
      expect(formatarDuracaoCurta(const Duration(hours: 26)), '1 dia');
    });
  });

  group('formatarPeriodoCurto', () {
    test('não repete a data quando começa e termina no mesmo dia', () {
      final texto = formatarPeriodoCurto(
        DateTime(2026, 8, 15, 20, 53),
        DateTime(2026, 8, 15, 21, 53),
      );
      expect(texto.contains('15/08'), isTrue);
      // A data aparece uma vez só - o fim é só o horário.
      expect('15/08'.allMatches(texto).length, 1);
    });
  });
}
