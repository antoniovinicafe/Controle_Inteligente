import 'api_client.dart';

/// Espelha as rotas de /api/faces do backend Flask.
///
/// O cadastro em si continua acontecendo dentro de `register_face_screen`
/// (que lida com câmera e bytes da imagem); isto aqui existe pra quem só
/// precisa saber se a pessoa já cadastrou o rosto.
class FacesService {
  /// Se o usuário logado já tem rosto cadastrado - ou `null` quando não deu
  /// pra perguntar (servidor fora do ar, endereço errado, rede caída).
  ///
  /// Nunca lança: derrubar a home inteira porque o backend piscou seria
  /// pior do que ficar sem a informação. Mas "não sei" e "não tem" são
  /// coisas diferentes, e quem chama é que decide o que fazer com cada uma:
  /// o aviso da home prefere calar a boca, a aba Rosto prefere admitir que
  /// não conseguiu verificar em vez de afirmar algo que não checou.
  static Future<bool?> status() async {
    try {
      final json = await ApiClient.get('/faces/status');
      return (json as Map<String, dynamic>)['cadastrado'] == true;
    } catch (_) {
      return null;
    }
  }
}
