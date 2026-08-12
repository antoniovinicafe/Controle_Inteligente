import '../models/frequencia.dart';
import '../models/perfil.dart';
import 'api_client.dart';

class UsuariosService {
  /// Busca usuários pra telas de "adicionar participante"/"adicionar aluno".
  /// Só professor/admin tem permissão nessa rota.
  static Future<List<Perfil>> buscar({String? busca, String? role}) async {
    final params = <String, String>{};
    if (busca != null && busca.trim().isNotEmpty) params['busca'] = busca.trim();
    if (role != null) params['role'] = role;

    final query = params.isEmpty
        ? ''
        : '?${params.entries.map((e) => '${e.key}=${Uri.encodeQueryComponent(e.value)}').join('&')}';

    final json = await ApiClient.get('/usuarios$query') as List;
    return json.map((e) => Perfil.fromJson(e as Map<String, dynamic>)).toList();
  }

  /// Presença do usuário logado nas aulas que já aconteceram.
  static Future<Frequencia> minhaFrequencia() async {
    final json = await ApiClient.get('/usuarios/me/frequencia');
    return Frequencia.fromJson(json as Map<String, dynamic>);
  }
}
