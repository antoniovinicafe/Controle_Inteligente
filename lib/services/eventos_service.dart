import '../models/access_log.dart';
import '../models/evento.dart';
import '../models/participante.dart';
import 'api_client.dart';

/// Espelha as rotas de /api/eventos do backend Flask.
class EventosService {
  static Future<List<Evento>> listar() async {
    final json = await ApiClient.get('/eventos') as List;
    return json.map((e) => Evento.fromJson(e as Map<String, dynamic>)).toList();
  }

  static Future<Evento> detalhe(int eventoId) async {
    final json = await ApiClient.get('/eventos/$eventoId');
    return Evento.fromJson(json as Map<String, dynamic>);
  }

  static Future<Evento> criar({
    required String titulo,
    String? descricao,
    String? local,
    required DateTime dataInicio,
    required DateTime dataFim,
    int? capacidade,
  }) async {
    final json = await ApiClient.post('/eventos', body: {
      'titulo': titulo,
      'descricao': descricao,
      'local': local,
      // toUtc().toIso8601String() garante o 'Z' no fim - o Postgres
      // guarda em timestamptz, então mandar sem timezone bagunçaria.
      'data_inicio': dataInicio.toUtc().toIso8601String(),
      'data_fim': dataFim.toUtc().toIso8601String(),
      'capacidade': capacidade,
    });
    return Evento.fromJson(json as Map<String, dynamic>);
  }

  static Future<Evento> editar(int eventoId, Map<String, dynamic> campos) async {
    final json = await ApiClient.patch('/eventos/$eventoId', body: campos);
    return Evento.fromJson(json as Map<String, dynamic>);
  }

  static Future<Evento> alterarStatus(int eventoId, String status) =>
      editar(eventoId, {'status': status});

  static Future<void> cancelar(int eventoId) => alterarStatus(eventoId, 'cancelado').then((_) {});

  /// Exclusão de verdade (apaga a linha). O backend recusa (409) se já
  /// existir algum access_log pra esse evento - nesse caso use [cancelar].
  static Future<void> excluir(int eventoId) async {
    await ApiClient.delete('/eventos/$eventoId');
  }

  // ---------------------------------------------------------------
  // Participantes
  // ---------------------------------------------------------------
  static Future<List<Participante>> listarParticipantes(int eventoId) async {
    final json = await ApiClient.get('/eventos/$eventoId/participantes') as List;
    return json
        .map((e) => Participante.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Aceita convidar por usuário e/ou por turma inteira (o backend
  /// "explode" a turma numa linha por aluno).
  static Future<int> convidar(
    int eventoId, {
    List<String> usuarioIds = const [],
    List<int> turmaIds = const [],
  }) async {
    final json = await ApiClient.post('/eventos/$eventoId/participantes', body: {
      'usuario_ids': usuarioIds,
      'turma_ids': turmaIds,
    });
    return ((json as Map<String, dynamic>)['total_convidados'] as num).toInt();
  }

  static Future<void> removerParticipante(int eventoId, String usuarioId) async {
    await ApiClient.delete('/eventos/$eventoId/participantes/$usuarioId');
  }

  /// Liberação manual - fallback pro reconhecimento facial.
  static Future<void> liberar(int eventoId, String usuarioId) async {
    await ApiClient.post('/eventos/$eventoId/participantes/$usuarioId/liberar');
  }

  // ---------------------------------------------------------------
  // Logs de acesso
  // ---------------------------------------------------------------
  static Future<List<AccessLog>> logs(int eventoId) async {
    final json = await ApiClient.get('/eventos/$eventoId/logs') as List;
    return json
        .map((e) => AccessLog.fromJson(e as Map<String, dynamic>))
        .toList();
  }
}
