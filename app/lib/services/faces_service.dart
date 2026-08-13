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

  /// As capturas da pessoa logada, da mais antiga pra mais nova.
  ///
  /// Lança em caso de erro (diferente de [contagem]): quem chama é a tela
  /// de rosto, que precisa dizer que não conseguiu carregar em vez de
  /// mostrar uma lista vazia — "você não tem capturas" e "não consegui
  /// perguntar" levam a ações opostas.
  static Future<List<Captura>> listar() async {
    final json = await ApiClient.get('/faces') as Map<String, dynamic>;
    return (json['capturas'] as List)
        .map((c) => Captura.doJson(c as Map<String, dynamic>))
        .toList();
  }

  /// Remove uma captura sem mexer nas outras.
  static Future<void> remover(int id) => ApiClient.delete('/faces/$id');
}

/// Uma foto cadastrada. Sem imagem: o servidor guarda só o vetor, então o
/// que dá pra mostrar é quando foi feita e o quanto ela se parece com as
/// outras da mesma pessoa.
class Captura {
  final int id;
  final DateTime? quando;

  /// Distância até a captura mais próxima das outras suas. Null quando é a
  /// única. Quanto menor, mais parecida.
  final double? distanciaIrma;

  /// O servidor achou que esta captura não parece as suas outras — pelo
  /// mesmo critério que usa pra recusar uma foto nova. Quem decide é ele:
  /// duplicar o limiar aqui seria criar uma segunda opinião pra divergir.
  final bool estranha;

  const Captura({
    required this.id,
    required this.quando,
    required this.distanciaIrma,
    required this.estranha,
  });

  factory Captura.doJson(Map<String, dynamic> j) => Captura(
        id: (j['id'] as num).toInt(),
        quando: DateTime.tryParse(j['atualizado_em'] as String? ?? ''),
        distanciaIrma: (j['distancia_irma'] as num?)?.toDouble(),
        estranha: j['estranha'] == true,
      );
}

class ContagemRostos {
  final int total;
  final int maximo;

  const ContagemRostos({required this.total, required this.maximo});

  bool get temAlguma => total > 0;
  bool get podeAdicionar => total < maximo;
}
