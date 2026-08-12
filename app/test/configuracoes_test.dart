import 'package:flutter_test/flutter_test.dart';
import 'package:inatel_access/config/app_config.dart';
import 'package:inatel_access/services/configuracoes.dart';

// O que a pessoa digita na tela de ajustes quando o IP muda nunca vem no
// formato que o ApiClient espera. Se normalizar() quebrar, o sintoma é
// "não foi possível conectar" em telas aleatórias - longe da causa.
void main() {
  test('completa esquema e sufixo /api', () {
    expect(Configuracoes.normalizar('192.168.0.10:5000'),
        'http://192.168.0.10:5000/api');
  });

  test('preserva https e não duplica /api', () {
    expect(Configuracoes.normalizar('https://fetin.inatel.br/api'),
        'https://fetin.inatel.br/api');
  });

  test('tolera barras sobrando no fim', () {
    expect(Configuracoes.normalizar('http://10.0.0.5:5000/api///'),
        'http://10.0.0.5:5000/api');
  });

  test('ignora espaços em volta', () {
    expect(Configuracoes.normalizar('   192.168.1.7:5000   '),
        'http://192.168.1.7:5000/api');
  });

  test('campo vazio volta pro padrão de fábrica', () {
    expect(Configuracoes.normalizar('  '), AppConfig.apiBaseUrl);
  });
}
