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
  /// Frequência por disciplina, que é a que decide aprovação. O agregado
  /// vem junto na mesma resposta, mas quem reprova ou não é a linha da
  /// turma - 80% somado pode esconder 50% numa matéria só.
  static Future<({Frequencia geral, List<FrequenciaDaTurma> turmas})>
      minhaFrequencia() async {
    final json = await ApiClient.get('/usuarios/me/frequencia') as Map<String, dynamic>;
    return (
      geral: Frequencia.fromJson(json),
      turmas: ((json['turmas'] as List?) ?? [])
          .map((t) => FrequenciaDaTurma.fromJson(t as Map<String, dynamic>))
          .toList(),
    );
  }
}
