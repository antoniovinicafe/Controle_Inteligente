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
  /// Texto do consentimento e se a pessoa já concordou com ELE.
  ///
  /// O texto vem do servidor, não embutido aqui: um APK antigo mostraria
  /// uma versão diferente da que o servidor registra, e corrigir uma frase
  /// passaria a exigir publicar app novo.
  static Future<Consentimento> consentimento() async {
    final json = await ApiClient.get('/usuarios/me/consentimento');
    return Consentimento.doJson(json as Map<String, dynamic>);
  }

  /// Registra que a pessoa concordou. A versão é decidida pelo servidor.
  static Future<void> consentir() =>
      ApiClient.post('/usuarios/me/consentimento');

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

/// O consentimento pro uso do rosto, como o servidor o descreve.
///
/// O texto e a versão vêm de lá porque é lá que ficam registrados: se o app
/// mostrasse um texto próprio, a pessoa concordaria com uma coisa e o banco
/// guardaria outra.
class Consentimento {
  final String versao;
  final String titulo;
  final String texto;

  /// Falta concordar — por nunca ter concordado, por ter revogado, ou por
  /// ter concordado com uma versão anterior do texto.
  final bool precisaConsentir;

  final DateTime? aceitoEm;

  const Consentimento({
    required this.versao,
    required this.titulo,
    required this.texto,
    required this.precisaConsentir,
    required this.aceitoEm,
  });

  factory Consentimento.doJson(Map<String, dynamic> j) => Consentimento(
        versao: j['versao'] as String,
        titulo: j['titulo'] as String,
        texto: j['texto'] as String,
        precisaConsentir: j['precisa_consentir'] == true,
        aceitoEm: j['aceito_em'] is String
            ? DateTime.parse(j['aceito_em'] as String).toLocal()
            : null,
      );
}
