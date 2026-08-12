import '../models/frequencia.dart';
import '../models/perfil.dart';
import '../models/turma.dart';
import 'api_client.dart';

/// Espelha as rotas de /api/turmas do backend Flask.
class TurmasService {
  static Future<List<Turma>> listar() async {
    final json = await ApiClient.get('/turmas') as List;
    return json.map((e) => Turma.fromJson(e as Map<String, dynamic>)).toList();
  }

  static Future<Turma> criar(String nome) async {
    final json = await ApiClient.post('/turmas', body: {'nome': nome});
    return Turma.fromJson(json as Map<String, dynamic>);
  }

  static Future<List<Perfil>> listarAlunos(int turmaId) async {
    final json = await ApiClient.get('/turmas/$turmaId/alunos') as List;
    // Essa rota não devolve `role` (só id/nome/matricula), então
    // completamos com 'aluno' - é o que a tela precisa exibir.
    return json
        .map((e) => Perfil.fromJson({
              ...e as Map<String, dynamic>,
              'role': 'aluno',
            }))
        .toList();
  }

  static Future<void> adicionarAlunos(int turmaId, List<String> alunoIds) async {
    await ApiClient.post('/turmas/$turmaId/alunos', body: {'aluno_ids': alunoIds});
  }

  static Future<void> removerAluno(int turmaId, String alunoId) async {
    await ApiClient.delete('/turmas/$turmaId/alunos/$alunoId');
  }

  /// Presença de cada aluno da turma nas aulas já encerradas.
  static Future<List<AlunoFrequencia>> frequencia(int turmaId) async {
    final json = await ApiClient.get('/turmas/$turmaId/frequencia') as List;
    return json
        .map((e) => AlunoFrequencia.fromJson(e as Map<String, dynamic>))
        .toList();
  }
}
