import 'package:shared_preferences/shared_preferences.dart';

import '../config/app_config.dart';

/// Ajustes que o usuário pode mudar sem recompilar o app.
///
/// Existe por um motivo prático: o endereço do servidor Flask entrava no
/// APK em tempo de compilação (`--dart-define`), então bastava o IP da
/// máquina mudar - trocar de Wi-Fi, o roteador renovar o DHCP - pra o app
/// parar de conectar e só voltar com um build novo. Na semana da feira
/// isso é o tipo de coisa que derruba a demonstração sem aviso.
///
/// O valor compilado continua sendo o padrão; o que está salvo aqui
/// apenas o sobrescreve.
class Configuracoes {
  static const _chaveApi = 'api_base_url';

  static SharedPreferences? _prefs;
  static String _apiBaseUrl = AppConfig.apiBaseUrl;

  /// Endereço em uso agora. Leitura síncrona de propósito: o ApiClient
  /// consulta isso a cada request e não pode ser assíncrono.
  static String get apiBaseUrl => _apiBaseUrl;

  /// True quando o usuário trocou o endereço na tela de ajustes.
  static bool get personalizado => _apiBaseUrl != AppConfig.apiBaseUrl;

  static String get padraoDeFabrica => AppConfig.apiBaseUrl;

  /// Chame antes do runApp - senão o primeiro request sai com o padrão.
  static Future<void> carregar() async {
    _prefs = await SharedPreferences.getInstance();
    final salvo = _prefs!.getString(_chaveApi);
    if (salvo != null && salvo.isNotEmpty) _apiBaseUrl = salvo;
  }

  static Future<void> definirApiBaseUrl(String url) async {
    _apiBaseUrl = normalizar(url);
    await _prefs?.setString(_chaveApi, _apiBaseUrl);
  }

  static Future<void> restaurarPadrao() async {
    _apiBaseUrl = AppConfig.apiBaseUrl;
    await _prefs?.remove(_chaveApi);
  }

  /// Aceita o que a pessoa realmente digita ("192.168.0.10:5000",
  /// "http://192.168.0.10:5000/api/") e devolve algo que o ApiClient
  /// consegue usar. Sem isso o erro só apareceria depois, como uma falha
  /// de rede genérica, e ninguém ligaria uma coisa à outra.
  static String normalizar(String bruto) {
    var url = bruto.trim();
    if (url.isEmpty) return AppConfig.apiBaseUrl;
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      url = 'http://$url';
    }
    while (url.endsWith('/')) {
      url = url.substring(0, url.length - 1);
    }
    if (!url.endsWith('/api')) url = '$url/api';
    return url;
  }
}
