import 'package:flutter_test/flutter_test.dart';
import 'package:inatel_access/models/recorrencia.dart';

/// A tela de criar aula recorrente promete um número ("vai criar 12 aulas")
/// antes de mandar a regra pro servidor, que faz a própria expansão. Se as
/// duas contas discordarem o app mente, então a conta do lado do app tem
/// que estar presa por teste.
///
/// Referência: o mesmo caso que foi validado por curl contra o backend na
/// sessão em que a recorrência foi construída - seg+qua num intervalo de
/// 8 dias gerou exatamente 3 eventos.
void main() {
  // 2026-08-10 é uma segunda-feira.
  final segunda = DateTime(2026, 8, 10);

  test('seg+qua em 8 dias dá 3 aulas (o caso conferido contra o backend)', () {
    // 10/08 seg, 12/08 qua, 17/08 seg - 19/08 qua já cai fora do intervalo.
    expect(contarOcorrencias({1, 3}, segunda, DateTime(2026, 8, 17)), 3);
  });

  test('conta os dois extremos do intervalo', () {
    // Segunda a segunda, só segundas: a de abertura e a de fechamento.
    expect(contarOcorrencias({1}, segunda, DateTime(2026, 8, 17)), 2);
  });

  test('um único dia que bate conta 1', () {
    expect(contarOcorrencias({1}, segunda, segunda), 1);
  });

  test('um único dia que não bate conta 0', () {
    expect(contarOcorrencias({3}, segunda, segunda), 0);
  });

  test('sem dia escolhido não gera nada', () {
    expect(contarOcorrencias({}, segunda, DateTime(2026, 12, 31)), 0);
  });

  test('intervalo invertido não gera nada em vez de estourar', () {
    expect(contarOcorrencias({1}, DateTime(2026, 8, 17), segunda), 0);
  });

  test('hora sobrando não corta o último dia', () {
    // Início às 23h e fim às 8h do mesmo dia seguinte: comparar sem
    // normalizar pra meia-noite deixaria o último dia de fora.
    final inicio = DateTime(2026, 8, 10, 23, 0);
    final fim = DateTime(2026, 8, 11, 8, 0);
    expect(contarOcorrencias({1, 2}, inicio, fim), 2);
  });

  test('semestre inteiro de seg/qua/sex fecha a conta', () {
    // 10/08 (seg) a 11/12/2026 (sex): 18 semanas cheias de seg-qua-sex.
    final total = contarOcorrencias({1, 3, 5}, segunda, DateTime(2026, 12, 11));
    expect(total, 54);
  });

  test('atravessa a virada do mês sem pular data', () {
    // 28/08 (sex) a 04/09 (sex), só sextas: 28/08 e 04/09.
    expect(
      contarOcorrencias({5}, DateTime(2026, 8, 28), DateTime(2026, 9, 4)),
      2,
    );
  });

  test('todos os dias da semana conta o intervalo inteiro', () {
    expect(
      contarOcorrencias({1, 2, 3, 4, 5, 6, 7}, segunda, DateTime(2026, 8, 16)),
      7,
    );
  });
}
