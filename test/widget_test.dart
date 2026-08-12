// Smoke test básico do projeto.
//
// FetinApp inicializa o Supabase dentro de main() antes de rodar
// (Supabase.initialize precisa de rede/credenciais), então não dá
// pra testar o widget raiz aqui sem mockar o SupabaseClient. Por
// enquanto isso só garante que o ambiente de teste do Flutter está
// funcionando; testes de widget de verdade (login, home, etc.)
// entram quando a Etapa 2 tiver telas com lógica própria pra testar.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('ambiente de teste do Flutter funciona', (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(body: Text('Fetin')),
      ),
    );

    expect(find.text('Fetin'), findsOneWidget);
  });
}
