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
    return (await contagem())?.temAlguma;
  }

  /// Quantas fotos a pessoa tem cadastradas, e o teto. Null quando não deu
  /// pra perguntar.
  static Future<ContagemRostos?> contagem() async {
    try {
      final json = await ApiClient.get('/faces/status') as Map<String, dynamic>;
      return ContagemRostos(
        // `total` só existe no backend novo; se o servidor for mais antigo,
        // cai pro booleano que sempre existiu.
        total: (json['total'] as num?)?.toInt() ??
            (json['cadastrado'] == true ? 1 : 0),
        maximo: (json['maximo'] as num?)?.toInt() ?? 1,
      );
    } catch (_) {
      return null;
    }
  }
}

class ContagemRostos {
  final int total;
  final int maximo;

  const ContagemRostos({required this.total, required this.maximo});

  bool get temAlguma => total > 0;
  bool get podeAdicionar => total < maximo;
}
