import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:supabase_flutter/supabase_flutter.dart';

import 'configuracoes.dart';

class ApiException implements Exception {
  final int statusCode;
  final String mensagem;
  ApiException(this.statusCode, this.mensagem);

  @override
  String toString() => mensagem;
}

/// Wrapper fino sobre o pacote http: monta a URL, anexa o
/// "Authorization: Bearer <token>" do Supabase, e já decodifica o JSON.
class ApiClient {
  static String? get _token =>
      Supabase.instance.client.auth.currentSession?.accessToken;

  static Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        if (_token != null) 'Authorization': 'Bearer $_token',
      };

  // Lido a cada request (e não guardado numa constante) porque o usuário
  // pode trocar o endereço do servidor nos ajustes com o app aberto.
  static Uri _uri(String path) => Uri.parse('${Configuracoes.apiBaseUrl}$path');

  /// Sem isso, um servidor fora do ar (ou uma rede que caiu no meio) deixa
  /// a tela girando pra sempre, porque o pacote http não tem timeout
  /// padrão. Upload de foto usa um limite maior - a imagem é grande e o
  /// DeepFace demora pra responder.
  static const _timeout = Duration(seconds: 15);
  static const _timeoutUpload = Duration(seconds: 60);

  /// Traduz as falhas de transporte em ApiException, pra UI ter uma
  /// mensagem em português em vez de "SocketException: ...".
  static Future<T> _comRede<T>(Future<T> Function() acao, Duration limite) async {
    try {
      return await acao().timeout(limite);
    } on TimeoutException {
      throw ApiException(0, 'O servidor demorou demais pra responder. '
          'Verifique se ele está no ar e tente de novo.');
    } on SocketException {
      throw ApiException(0, 'Não foi possível conectar ao servidor. '
          'Confira sua conexão e o endereço da API.');
    } on http.ClientException {
      throw ApiException(0, 'A conexão com o servidor falhou no meio. '
          'Tente de novo.');
    }
  }

  static dynamic _handle(http.Response resp) {
    final corpo = resp.body.isNotEmpty ? jsonDecode(resp.body) : null;
    if (resp.statusCode >= 200 && resp.statusCode < 300) {
      return corpo;
    }
    final mensagem = (corpo is Map && corpo['erro'] != null)
        ? corpo['erro'] as String
        : 'Erro inesperado (${resp.statusCode})';
    throw ApiException(resp.statusCode, mensagem);
  }

  static Future<dynamic> get(String path) async {
    final resp = await _comRede(
      () => http.get(_uri(path), headers: _headers),
      _timeout,
    );
    return _handle(resp);
  }

  static Future<dynamic> post(String path, {Map<String, dynamic>? body}) async {
    final resp = await _comRede(
      () => http.post(
        _uri(path),
        headers: _headers,
        body: body != null ? jsonEncode(body) : null,
      ),
      _timeout,
    );
    return _handle(resp);
  }

  static Future<dynamic> patch(String path, {Map<String, dynamic>? body}) async {
    final resp = await _comRede(
      () => http.patch(
        _uri(path),
        headers: _headers,
        body: body != null ? jsonEncode(body) : null,
      ),
      _timeout,
    );
    return _handle(resp);
  }

  static Future<dynamic> delete(String path) async {
    final resp = await _comRede(
      () => http.delete(_uri(path), headers: _headers),
      _timeout,
    );
    return _handle(resp);
  }

  /// Upload de arquivo (usado no cadastro de rosto, etapa 2)
  static Future<dynamic> postMultipart(
    String path, {
    required String campoArquivo,
    required List<int> bytes,
    required String nomeArquivo,
  }) async {
    final request = http.MultipartRequest('POST', _uri(path));
    if (_token != null) request.headers['Authorization'] = 'Bearer $_token';
    request.files.add(http.MultipartFile.fromBytes(
      campoArquivo,
      bytes,
      filename: nomeArquivo,
    ));
    final resp = await _comRede(
      () async => http.Response.fromStream(await request.send()),
      _timeoutUpload,
    );
    return _handle(resp);
  }
}
