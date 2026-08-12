import 'package:flutter/foundation.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../models/perfil.dart';
import 'api_client.dart';

enum AuthStatus {
  carregando, // checando se já tem sessão salva
  deslogado,
  logadoSemPerfil, // logou no Supabase mas ainda não preencheu profiles
  logado,
}

class AuthProvider extends ChangeNotifier {
  AuthStatus status = AuthStatus.carregando;
  Perfil? perfil;
  String? erro;

  AuthProvider() {
    _init();
  }

  SupabaseClient get _client => Supabase.instance.client;

  Future<void> _init() async {
    _client.auth.onAuthStateChange.listen((data) async {
      final session = data.session;
      if (session == null) {
        status = AuthStatus.deslogado;
        perfil = null;
        notifyListeners();
        return;
      }
      await _carregarPerfil();
    });

    // Sessão pode já existir ao abrir o app (usuário logou antes)
    if (_client.auth.currentSession != null) {
      await _carregarPerfil();
    } else {
      status = AuthStatus.deslogado;
      notifyListeners();
    }
  }

  Future<void> _carregarPerfil() async {
    try {
      final json = await ApiClient.get('/usuarios/me');
      perfil = Perfil.fromJson(json);
      status = AuthStatus.logado;
    } on ApiException catch (e) {
      // 404 aqui significa: logou no Supabase mas ainda não tem
      // registro em `profiles` -> precisa completar cadastro
      if (e.statusCode == 404) {
        status = AuthStatus.logadoSemPerfil;
      } else {
        erro = e.mensagem;
        status = AuthStatus.deslogado;
      }
    } catch (e) {
      // Qualquer outro erro (rede fora do ar, timeout, resposta que não
      // é nem 2xx nem um erro JSON da nossa API) - sem isso aqui a tela
      // ficava travada em "carregando" pra sempre, sem feedback nenhum.
      debugPrint('Erro inesperado ao carregar perfil: $e');
      erro = 'Não foi possível conectar ao servidor. Tente novamente.';
      status = AuthStatus.deslogado;
    }
    notifyListeners();
  }

  Future<void> login(String email, String senha) async {
    erro = null;
    try {
      await _client.auth.signInWithPassword(email: email, password: senha);
      // o listener do onAuthStateChange já dispara _carregarPerfil()
    } on AuthException catch (e) {
      erro = e.message;
      notifyListeners();
      rethrow;
    }
  }

  Future<void> cadastrar(String email, String senha) async {
    erro = null;
    try {
      await _client.auth.signUp(email: email, password: senha);
    } on AuthException catch (e) {
      erro = e.message;
      notifyListeners();
      rethrow;
    }
  }

  Future<void> completarCadastro({
    required String nome,
    required String matricula,
    required String role,
  }) async {
    final json = await ApiClient.post('/usuarios/complete-cadastro', body: {
      'nome': nome,
      'matricula': matricula,
      'role': role,
    });
    perfil = Perfil.fromJson(json);
    status = AuthStatus.logado;
    notifyListeners();
  }

  Future<void> logout() async {
    await _client.auth.signOut();
    perfil = null;
    status = AuthStatus.deslogado;
    notifyListeners();
  }
}
