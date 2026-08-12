import '../models/recorrencia.dart';
import 'api_client.dart';

class RecorrenciasService {
  static Future<Map<String, dynamic>> criar({
    required int turmaId,
    required String titulo,
    String? descricao,
    String? local,
    int? capacidade,
    required List<int> diasSemana,
    required String horaInicio, // "HH:MM"
    required String horaFim,
    required DateTime dataInicio,
    required DateTime dataFim,
  }) async {
    final json = await ApiClient.post('/recorrencias', body: {
      'turma_id': turmaId,
      'titulo': titulo,
      'descricao': descricao,
      'local': local,
      'capacidade': capacidade,
      'dias_semana': diasSemana,
      'hora_inicio': horaInicio,
      'hora_fim': horaFim,
      'data_inicio': _dataIso(dataInicio),
      'data_fim': _dataIso(dataFim),
    });
    return json as Map<String, dynamic>;
  }

  static Future<List<Recorrencia>> listar() async {
    final json = await ApiClient.get('/recorrencias') as List;
    return json.map((e) => Recorrencia.fromJson(e as Map<String, dynamic>)).toList();
  }

  /// Cancela só as ocorrências futuras da série. Devolve quantas foram canceladas.
  static Future<int> cancelar(int recorrenciaId) async {
    final json = await ApiClient.delete('/recorrencias/$recorrenciaId');
    return ((json as Map<String, dynamic>)['eventos_cancelados'] as num).toInt();
  }

  static String _dataIso(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
}
