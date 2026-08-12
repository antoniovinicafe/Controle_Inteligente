import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config/tema.dart';
import '../services/auth_provider.dart';
import '../services/configuracoes.dart';
import 'configuracoes_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailCtrl = TextEditingController();
  final _senhaCtrl = TextEditingController();

  bool _modoCadastro = false;
  bool _carregando = false;

  Future<void> _enviar() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _carregando = true);

    final auth = context.read<AuthProvider>();
    try {
      if (_modoCadastro) {
        await auth.cadastrar(_emailCtrl.text.trim(), _senhaCtrl.text);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
            content: Text('Conta criada! Verifique seu email para confirmar, se necessário.'),
          ));
        }
      } else {
        await auth.login(_emailCtrl.text.trim(), _senhaCtrl.text);
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(auth.erro ?? 'Erro ao autenticar'),
          backgroundColor: CoresStatus.erro(context),
        ));
      }
    } finally {
      if (mounted) setState(() => _carregando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    // context.watch aqui: se o erro vier depois do login em si (ex: falha
    // ao carregar o perfil, disparada pelo listener do Supabase), a tela
    // de login precisa reagir mesmo sem estar mais dentro do _enviar().
    final erroCarregarPerfil = context.watch<AuthProvider>().erro;

    final cores = Theme.of(context).colorScheme;

    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 24),
            child: Form(
              key: _formKey,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // Marca própria em vez de ícone-de-tutorial + título
                  // centralizado - alinhado à esquerda, o "F" carrega o
                  // peso visual que antes vinha de um Icon genérico.
                  // Align obrigatório: a Column usa crossAxisAlignment.stretch
                  // (pros campos e botões ocuparem a largura), e stretch passa
                  // por cima do width:52 - a marca virava uma faixa da tela
                  // inteira com um "F" no meio.
                  Align(
                    alignment: Alignment.centerLeft,
                    child: Container(
                      width: 52,
                      height: 52,
                      decoration: BoxDecoration(
                        color: cores.primary,
                        borderRadius: BorderRadius.circular(14),
                      ),
                      alignment: Alignment.center,
                      child: Text(
                        'F',
                        style: TextStyle(
                          color: cores.onPrimary,
                          fontSize: 26,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 20),
                  Text(
                    'Fetin',
                    style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                          fontWeight: FontWeight.w600,
                          letterSpacing: -0.5,
                        ),
                  ),
                  const SizedBox(height: 5),
                  // Diz o que o sistema é, não o que o formulário faz - "Entre
                  // na sua conta" logo acima de um campo de email e um botão
                  // "Entrar" é legenda de coisa auto-evidente. Quem abre o app
                  // pela primeira vez ganha mais sabendo o que ele controla.
                  Text(
                    'Controle de acesso por reconhecimento facial',
                    style: TextStyle(
                      fontSize: 14.5,
                      height: 1.35,
                      color: cores.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: 34),
                  TextFormField(
                    controller: _emailCtrl,
                    keyboardType: TextInputType.emailAddress,
                    decoration: const InputDecoration(labelText: 'Email'),
                    validator: (v) =>
                        (v == null || !v.contains('@')) ? 'Email inválido' : null,
                  ),
                  const SizedBox(height: 14),
                  TextFormField(
                    controller: _senhaCtrl,
                    obscureText: true,
                    decoration: const InputDecoration(labelText: 'Senha'),
                    validator: (v) =>
                        (v == null || v.length < 6) ? 'Mínimo 6 caracteres' : null,
                  ),
                  const SizedBox(height: 22),
                  FilledButton(
                    onPressed: _carregando ? null : _enviar,
                    child: _carregando
                        ? const SizedBox(
                            height: 20,
                            width: 20,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : Text(_modoCadastro ? 'Criar conta' : 'Entrar'),
                  ),
                  const SizedBox(height: 14),
                  TextButton(
                    onPressed: () => setState(() => _modoCadastro = !_modoCadastro),
                    child: Text(_modoCadastro
                        ? 'Já tenho conta - fazer login'
                        : 'Não tenho conta - criar uma'),
                  ),
                  if (erroCarregarPerfil != null) ...[
                    const SizedBox(height: 4),
                    Text(
                      erroCarregarPerfil,
                      textAlign: TextAlign.center,
                      style: TextStyle(color: CoresStatus.erro(context), fontSize: 13),
                    ),
                  ],
                  const SizedBox(height: 32),
                  // Entrar valida a senha no Supabase (nuvem), mas carregar o
                  // perfil bate no Flask da rede local - então dá pra logar
                  // "com sucesso" e mesmo assim travar, se o endereço estiver
                  // velho. Como o IP da máquina muda sozinho quando o DHCP
                  // renova, mostrar o alvo aqui transforma o erro mais comum
                  // do projeto em algo que se resolve antes de acontecer.
                  const _RodapeServidor(),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Endereço do servidor no pé da tela de login, tocável pra ir aos ajustes.
///
/// É StatefulWidget só pra reler o valor ao voltar da tela de ajustes -
/// sem isso continuaria mostrando o endereço antigo até reabrir o app, que
/// é justamente a confusão que ele existe pra evitar.
class _RodapeServidor extends StatefulWidget {
  const _RodapeServidor();

  @override
  State<_RodapeServidor> createState() => _RodapeServidorState();
}

class _RodapeServidorState extends State<_RodapeServidor> {
  Future<void> _abrirAjustes() async {
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const ConfiguracoesScreen()),
    );
    if (mounted) setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final uri = Uri.tryParse(Configuracoes.apiBaseUrl);
    final host = (uri == null || uri.host.isEmpty)
        ? Configuracoes.apiBaseUrl
        : (uri.hasPort ? '${uri.host}:${uri.port}' : uri.host);

    return Center(
      child: InkWell(
        onTap: _abrirAjustes,
        borderRadius: BorderRadius.circular(8),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('SERVIDOR', style: Tipos.etiqueta(context).copyWith(fontSize: 10)),
              const SizedBox(width: 8),
              Text(host, style: Tipos.dado(context, tamanho: 11.5)),
            ],
          ),
        ),
      ),
    );
  }
}
