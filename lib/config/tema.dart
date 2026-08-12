import 'package:flutter/material.dart';

/// Nomes das famílias declaradas no pubspec. As fontes vão dentro do APK -
/// nada é baixado em tempo de execução, então a primeira abertura sem
/// internet mostra a mesma coisa que a décima com internet.
const _jost = 'Jost';
const _mono = 'IBMPlexMono';

/// Tema do Fetin.
///
/// A ideia é sumir: nada de sombra, card flutuante ou cor gritando. O que
/// dá forma à tela é espaçamento e hierarquia de texto, não caixa em volta
/// de tudo. Superfícies chapadas e tons neutros - o conteúdo é que precisa
/// aparecer.
///
/// DUAS VOZES
/// O app fala duas línguas e mostra isso na tipografia, igual ao leitor da
/// porta (que usa URW Gothic pra pessoa e DejaVu Mono pra máquina):
///
///   Jost           -> o que uma PESSOA escreveu: nome, título da aula, local
///   IBM Plex Mono  -> o que o SISTEMA registrou: matrícula, horário de
///                     entrada, contador, rótulo de seção
///
/// Não é enfeite: num controle de acesso a diferença entre "o que alguém
/// digitou" e "o que a catraca gravou" é justamente o que dá credibilidade
/// à tela. Ver isso sem precisar ler é o ponto.

/// Azul-petróleo. Foge do índigo/roxo padrão do Material 3 (a cara de
/// projeto recém-criado) e é o tom institucional do sistema - a mesma
/// semente que pinta o totem na porta.
const _semente = Color(0xFF15616D);

/// Cantos: generosos o bastante pra parecer intencional, discretos o
/// bastante pra não virar bolha.
const _raio = 14.0;

ThemeData temaFetin(Brightness brilho) {
  final escuro = brilho == Brightness.dark;
  final cores = ColorScheme.fromSeed(seedColor: _semente, brightness: brilho);

  // Fundo com fundo de petróleo em vez de cinza neutro: preto puro com um
  // acento claro é exatamente a cara de tema escuro genérico. O sub-tom
  // verde-azulado amarra com a marca sem ninguém notar conscientemente.
  final fundo = escuro ? const Color(0xFF0E1518) : const Color(0xFFF6F8F8);
  final superficie = escuro ? const Color(0xFF161F23) : Colors.white;

  final base = ThemeData(
    colorScheme: cores.copyWith(surface: fundo),
    useMaterial3: true,
    scaffoldBackgroundColor: fundo,
  );

  // Jost em cima da escala do Material: mantém tamanhos e pesos que o
  // Flutter já calcula, troca só o desenho das letras.
  final texto = base.textTheme.apply(
    fontFamily: _jost,
    bodyColor: cores.onSurface,
    displayColor: cores.onSurface,
  );

  return base.copyWith(
    textTheme: texto,
    appBarTheme: AppBarTheme(
      backgroundColor: fundo,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
      titleTextStyle: texto.titleLarge?.copyWith(
        fontWeight: FontWeight.w600,
        letterSpacing: -0.2,
      ),
    ),
    cardTheme: CardThemeData(
      elevation: 0,
      color: superficie,
      surfaceTintColor: Colors.transparent,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(_raio)),
    ),
    listTileTheme: ListTileThemeData(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(_raio)),
      titleTextStyle: texto.bodyLarge?.copyWith(fontWeight: FontWeight.w500),
      subtitleTextStyle: texto.bodySmall?.copyWith(
        color: cores.onSurfaceVariant,
        height: 1.35,
      ),
    ),
    dividerTheme: DividerThemeData(
      space: 1,
      thickness: 1,
      color: cores.outlineVariant.withValues(alpha: escuro ? 0.22 : 0.6),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: superficie,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      height: 66,
      indicatorColor: cores.primary.withValues(alpha: escuro ? 0.20 : 0.14),
      labelTextStyle: WidgetStateProperty.resolveWith(
        (estados) => texto.labelMedium?.copyWith(
          fontWeight: estados.contains(WidgetState.selected)
              ? FontWeight.w600
              : FontWeight.w400,
        ),
      ),
    ),
    // Chip sem borda e com fundo lavado: rótulo de status não deve competir
    // com o nome do que ele está rotulando.
    chipTheme: ChipThemeData(
      side: BorderSide.none,
      backgroundColor: cores.surfaceContainerHighest,
      labelStyle: texto.labelMedium?.copyWith(fontWeight: FontWeight.w600),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 2),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: superficie,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(_raio),
        borderSide: BorderSide.none,
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(_raio),
        borderSide: BorderSide(color: cores.outlineVariant.withValues(alpha: 0.5)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(_raio),
        borderSide: BorderSide(color: cores.primary, width: 1.5),
      ),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size.fromHeight(50),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(_raio)),
        textStyle: const TextStyle(fontFamily: _jost, fontSize: 15, fontWeight: FontWeight.w600),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        textStyle: const TextStyle(fontFamily: _jost, fontSize: 14.5, fontWeight: FontWeight.w600),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size.fromHeight(50),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(_raio)),
        textStyle: const TextStyle(fontFamily: _jost, fontSize: 15, fontWeight: FontWeight.w600),
      ),
    ),
    floatingActionButtonTheme: FloatingActionButtonThemeData(
      elevation: 0,
      highlightElevation: 0,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(_raio)),
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      contentTextStyle: const TextStyle(fontFamily: _jost, fontSize: 14.5),
    ),
    dialogTheme: DialogThemeData(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
      titleTextStyle: texto.titleLarge?.copyWith(fontWeight: FontWeight.w600),
    ),
  );
}

/// A voz da máquina.
///
/// Tudo que o sistema mediu, contou ou carimbou sai daqui - e só daqui.
/// Se você está em dúvida se um texto é [Tipos] ou tipografia normal,
/// pergunte: uma pessoa digitou isso? Se sim, não é [Tipos].
class Tipos {
  /// Rótulo de seção ("ENTRARAM · 7", "PRÓXIMA AULA"). Caixa alta e
  /// espaçada pra funcionar como régua entre blocos, sem virar título.
  static TextStyle etiqueta(BuildContext c, {Color? cor}) => TextStyle(
        fontFamily: _mono,
        fontSize: 11,
        fontWeight: FontWeight.w500,
        letterSpacing: 1.1,
        color: cor ?? Theme.of(c).colorScheme.onSurfaceVariant,
      );

  /// Matrícula, horário de entrada, contagem. Monoespaçado porque são
  /// registros: alinham em coluna e dá pra comparar de relance.
  static TextStyle dado(BuildContext c, {double tamanho = 12.5, Color? cor, FontWeight? peso}) =>
      TextStyle(
        fontFamily: _mono,
        fontSize: tamanho,
        fontWeight: peso ?? FontWeight.w400,
        color: cor ?? Theme.of(c).colorScheme.outline,
      );

  /// Número grande de painel (o "7" de "7 / 30 entraram").
  static TextStyle numeral(BuildContext c, {required Color cor, double tamanho = 44}) =>
      TextStyle(
        fontFamily: _mono,
        fontSize: tamanho,
        fontWeight: FontWeight.w500,
        height: 1,
        color: cor,
      );
}

/// Cores de status.
///
/// São exatamente as mesmas do leitor na porta: quem vê LIBERADO em menta
/// na catraca encontra o mesmo menta no app. `Colors.green`/`red` puros
/// seriam berrantes e, pior, diriam que app e porta são dois sistemas.
class CoresStatus {
  static Color ok(BuildContext c) => _tom(c, const Color(0xFF1E7A57), const Color(0xFF35D6A0));
  static Color alerta(BuildContext c) => _tom(c, const Color(0xFFB26A00), const Color(0xFFF0B45E));
  static Color erro(BuildContext c) => _tom(c, const Color(0xFFB3261E), const Color(0xFFF0655A));
  static Color neutro(BuildContext c) => Theme.of(c).colorScheme.onSurfaceVariant;

  static Color _tom(BuildContext c, Color claro, Color escuro) =>
      Theme.of(c).brightness == Brightness.dark ? escuro : claro;

  /// Fundo lavado pro mesmo tom, pra chip/selo.
  static Color fundo(BuildContext c, Color tom) =>
      tom.withValues(alpha: Theme.of(c).brightness == Brightness.dark ? 0.16 : 0.12);
}
