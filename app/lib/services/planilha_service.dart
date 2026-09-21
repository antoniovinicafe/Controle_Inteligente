import 'dart:io';

import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

import 'api_client.dart';

/// Baixa uma planilha da API e abre a folha de compartilhamento do sistema.
///
/// POR QUE COMPARTILHAR E NÃO SALVAR
/// Salvar numa pasta obrigaria a pessoa a achar o arquivo depois, e no
/// Android nem toda pasta é visível pro gerenciador de arquivos. A folha de
/// compartilhamento deixa ela escolher o destino que já ia usar de qualquer
/// jeito — e-mail, WhatsApp, Drive — em um toque, e é o mesmo gesto que ela
/// já conhece de qualquer outro app.
///
/// O arquivo fica na pasta temporária de propósito: ele é um retrato de um
/// momento, e guardar cópias antigas no aparelho só cria confusão sobre qual
/// é a atual. Quem precisa de arquivo permanente salva no destino que
/// escolheu.
class PlanilhaService {
  /// A lista de presença de uma aula.
  static Future<void> presencaDoEvento(int eventoId, String titulo) =>
      _baixarECompartilhar(
        '/eventos/$eventoId/presenca.csv',
        'presenca-${_nomeSeguro(titulo)}.csv',
        'Lista de presença — $titulo',
      );

  /// A frequência da turma inteira, que é a que decide aprovação.
  static Future<void> frequenciaDaTurma(int turmaId, String nome) =>
      _baixarECompartilhar(
        '/turmas/$turmaId/frequencia.csv',
        'frequencia-${_nomeSeguro(nome)}.csv',
        'Frequência — $nome',
      );

  static Future<void> _baixarECompartilhar(
    String rota,
    String nomeArquivo,
    String assunto,
  ) async {
    final bytes = await ApiClient.getBytes(rota);

    final pasta = await getTemporaryDirectory();
    final arquivo = File('${pasta.path}/$nomeArquivo');
    await arquivo.writeAsBytes(bytes);

    await SharePlus.instance.share(
      ShareParams(
        files: [XFile(arquivo.path, mimeType: 'text/csv')],
        subject: assunto,
      ),
    );
  }

  /// Tira do nome do arquivo o que o sistema de arquivos recusa.
  ///
  /// Título de aula é texto livre digitado pelo professor, e uma barra em
  /// "Cálculo I - 2026/2" faria o caminho apontar pra uma pasta que não
  /// existe. Acento pode ficar: o problema são os separadores.
  static String _nomeSeguro(String texto) => texto
      .replaceAll(RegExp(r'[\\/:*?"<>|]'), '-')
      .replaceAll(RegExp(r'\s+'), ' ')
      .trim();
}
