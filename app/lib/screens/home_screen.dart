import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config/tema.dart';
import '../services/auth_provider.dart';
import '../services/faces_service.dart';
import 'agora_screen.dart';
import 'configuracoes_screen.dart';
import 'eventos_screen.dart';
import 'register_face_screen.dart';
import 'turmas_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _aba = 0;

  // As abas ficam vivas dentro do IndexedStack, então a lista de eventos
  // carregaria só uma vez e nunca veria o que foi criado de outra aba
  // (ex: aula recorrente criada em Turmas gera eventos). Trocar a key ao
  // entrar na aba força a remontagem - mesmo padrão do ListaAsync.
  int _versaoEventos = 0;

  // Sem rosto cadastrado o reconhecimento nunca vai liberar essa pessoa -
  // e até agora o único caminho pra essa tela era uma aba que ninguém tinha
  // motivo pra abrir. O aviso fica sobre todas as abas até resolver.
  //
  // null = ainda não deu pra perguntar. O aviso some nesse caso (não vale
  // acusar ninguém de falta de cadastro por causa de um servidor offline),
  // mas a aba Rosto mostra o "não verificado" com todas as letras.
  bool? _temRosto;

  @override
  void initState() {
    super.initState();
    _conferirRosto();
  }

  Future<void> _conferirRosto() async {
    final status = await FacesService.status();
    if (mounted) setState(() => _temRosto = status);
  }

  Future<void> _abrirCadastroRosto() async {
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const RegisterFaceScreen()),
    );
    _conferirRosto(); // pode ter cadastrado lá dentro
  }

  // Eventos é a aba 1 (a 0 é Agora).
  static const _abaEventos = 1;

  void _selecionarAba(int i) => setState(() {
        if (i == _abaEventos && _aba != _abaEventos) _versaoEventos++;
        _aba = i;
      });

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final perfil = auth.perfil!;
    final ehProfessor = perfil.isProfessor;
    final cores = Theme.of(context).colorScheme;

    final rosto = _RostoTab(
      temRosto: _temRosto,
      onCadastrar: _abrirCadastroRosto,
      onVerificar: _conferirRosto,
    );

    // Aluno não tem turmas pra gerenciar - só Agora, Eventos e Rosto.
    final abas = ehProfessor
        ? [
            AgoraScreen(ativo: _aba == 0),
            EventosScreen(key: ValueKey(_versaoEventos)),
            const TurmasScreen(),
            rosto,
          ]
        : [
            AgoraScreen(ativo: _aba == 0),
            EventosScreen(key: ValueKey(_versaoEventos)),
            rosto,
          ];

    return Scaffold(
      appBar: AppBar(
        titleSpacing: 20,
        // Duas linhas em vez de "Olá, Fulano" solto: o nome é o que a
        // pessoa escreveu (Jost), o papel é o que o sistema atribuiu a ela
        // (mono). É a mesma divisão de vozes do resto do app, e resolve uma
        // dúvida real - professor e aluno veem telas diferentes, então
        // saber em que papel você está logado importa.
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(perfil.nome.split(' ').first),
            const SizedBox(height: 1),
            Text(
              ehProfessor ? 'PROFESSOR' : 'ALUNO',
              style: Tipos.etiqueta(context, cor: cores.outline).copyWith(fontSize: 10),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            tooltip: 'Ajustes',
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const ConfiguracoesScreen()),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: 'Sair',
            onPressed: () => context.read<AuthProvider>().logout(),
          ),
        ],
      ),
      body: Column(
        children: [
          if (_temRosto == false) _AvisoRosto(onTocar: _abrirCadastroRosto),
          Expanded(child: IndexedStack(index: _aba, children: abas)),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _aba,
        onDestinationSelected: _selecionarAba,
        destinations: [
          const NavigationDestination(icon: Icon(Icons.sensors), label: 'Agora'),
          const NavigationDestination(icon: Icon(Icons.event_outlined), label: 'Eventos'),
          if (ehProfessor)
            const NavigationDestination(icon: Icon(Icons.groups_outlined), label: 'Turmas'),
          const NavigationDestination(icon: Icon(Icons.face_outlined), label: 'Rosto'),
        ],
      ),
    );
  }
}

/// Faixa que fica sobre todas as abas enquanto a pessoa não cadastrou o
/// rosto. É a única coisa no app que empurra pra esse cadastro - sem ele
/// a câmera da porta nunca reconhece ninguém.
class _AvisoRosto extends StatelessWidget {
  final VoidCallback onTocar;

  const _AvisoRosto({required this.onTocar});

  @override
  Widget build(BuildContext context) {
    final cor = CoresStatus.alerta(context);
    return Material(
      color: CoresStatus.fundo(context, cor),
      child: InkWell(
        onTap: onTocar,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 11, 12, 12),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // A etiqueta faz o trabalho que o ícone fazia, e diz
                    // mais: nomeia o estado em vez de só ilustrá-lo.
                    Text('ROSTO NÃO CADASTRADO', style: Tipos.etiqueta(context, cor: cor)),
                    const SizedBox(height: 3),
                    Text(
                      'A porta não vai te reconhecer',
                      style: TextStyle(
                        color: cor,
                        fontWeight: FontWeight.w500,
                        fontSize: 13.5,
                      ),
                    ),
                  ],
                ),
              ),
              Icon(Icons.chevron_right, color: cor, size: 20),
            ],
          ),
        ),
      ),
    );
  }
}

/// Aba Rosto.
///
/// Antes era um convite genérico ("cadastre seu rosto") mostrado do mesmo
/// jeito pra quem já tinha cadastrado e pra quem não tinha - ou seja, a
/// única tela sobre o seu cadastro facial não sabia dizer se você tinha um.
/// Agora ela responde primeiro a pergunta que a pessoa veio fazer, e só
/// depois oferece a ação que couber.
class _RostoTab extends StatelessWidget {
  /// null = não deu pra verificar.
  final bool? temRosto;
  final VoidCallback onCadastrar;
  final VoidCallback onVerificar;

  const _RostoTab({
    required this.temRosto,
    required this.onCadastrar,
    required this.onVerificar,
  });

  @override
  Widget build(BuildContext context) {
    final cores = Theme.of(context).colorScheme;

    final (cor, rotulo, titulo, explicacao) = switch (temRosto) {
      true => (
          CoresStatus.ok(context),
          'CADASTRADO',
          'A porta reconhece você',
          'Chegue na frente da câmera durante uma aula sua e a entrada é '
              'registrada sozinha.',
        ),
      false => (
          CoresStatus.alerta(context),
          'NÃO CADASTRADO',
          'A porta não reconhece você',
          'Sem uma foto cadastrada o leitor não tem com o que comparar, '
              'e sua presença não é registrada.',
        ),
      null => (
          cores.outline,
          'NÃO VERIFICADO',
          'Não deu pra consultar o servidor',
          'O cadastro pode existir - o app é que não conseguiu perguntar.',
        ),
    };

    // O bloco de privacidade fica colado no rodapé (Spacer), mas a tela
    // ainda precisa rolar num aparelho baixo ou com fonte ampliada nas
    // acessibilidades - Spacer sozinho dentro de scroll não compila, e sem
    // scroll a coluna estoura. Este trio resolve os dois lados: rola quando
    // falta espaço, empurra pro rodapé quando sobra.
    return SafeArea(
      child: LayoutBuilder(
        builder: (context, restricoes) => SingleChildScrollView(
          child: ConstrainedBox(
            constraints: BoxConstraints(minHeight: restricoes.maxHeight),
            child: IntrinsicHeight(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(20, 28, 20, 20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        // Ponto de status: o mesmo vocabulário do totem na porta,
                        // onde a cor é que carrega o veredito.
                        Container(
                          width: 7,
                          height: 7,
                          decoration: BoxDecoration(color: cor, shape: BoxShape.circle),
                        ),
                        const SizedBox(width: 9),
                        Text(rotulo, style: Tipos.etiqueta(context, cor: cor)),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Text(
                      titulo,
                      style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                            fontWeight: FontWeight.w500,
                            letterSpacing: -0.3,
                          ),
                    ),
                    const SizedBox(height: 10),
                    Text(
                      explicacao,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                            color: cores.onSurfaceVariant,
                            height: 1.45,
                          ),
                    ),
                    const SizedBox(height: 28),
                    if (temRosto == null)
                      OutlinedButton.icon(
                        onPressed: onVerificar,
                        icon: const Icon(Icons.refresh, size: 18),
                        label: const Text('Verificar de novo'),
                      )
                    else if (temRosto == false)
                      FilledButton.icon(
                        onPressed: onCadastrar,
                        icon: const Icon(Icons.camera_alt_outlined, size: 18),
                        label: const Text('Cadastrar meu rosto'),
                      )
                    else
                      OutlinedButton.icon(
                        onPressed: onCadastrar,
                        icon: const Icon(Icons.camera_alt_outlined, size: 18),
                        label: const Text('Atualizar minha foto'),
                      ),
                    const Spacer(),
                    // Um sistema que guarda o rosto das pessoas deve dizer o que
                    // guarda, mesmo que ninguém pergunte.
                    Text('O QUE FICA GUARDADO', style: Tipos.etiqueta(context)),
                    const SizedBox(height: 6),
                    // Só o que o backend de fato garante: routes/faces.py grava
                    // apenas (usuario_id, embedding, modelo) e descarta os bytes da
                    // imagem. Evitar prometer que o vetor é irreversível - inverter
                    // embedding de rosto é um ataque conhecido na literatura, e não
                    // é uma promessa que este projeto pode fazer.
                    Text(
                      'Só um vetor de números extraído da foto, ligado à sua conta. '
                      'A imagem não é gravada nem no servidor nem no leitor da porta: '
                      'ela é usada pra gerar o vetor e descartada.',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: cores.outline,
                            height: 1.5,
                          ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
