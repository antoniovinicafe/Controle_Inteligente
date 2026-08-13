import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config/tema.dart';
import '../models/frequencia.dart';
import '../models/perfil.dart';
import '../models/turma.dart';
import 'eventos_screen.dart' show Selo, corDaFrequencia;
import '../services/auth_provider.dart';
import '../services/turmas_service.dart';
import '../widgets/lista_async.dart';
import 'criar_recorrencia_screen.dart';
import 'selecionar_usuarios_screen.dart';

class TurmaDetailScreen extends StatefulWidget {
  final Turma turma;

  const TurmaDetailScreen({super.key, required this.turma});

  @override
  State<TurmaDetailScreen> createState() => _TurmaDetailScreenState();
}

class _TurmaDetailScreenState extends State<TurmaDetailScreen> {
  int _versao = 0;
  // Marca se alguma alteração foi feita, pra tela anterior saber recarregar.
  bool _mudou = false;

  void _recarregar() => setState(() => _versao++);

  Future<void> _adicionarAlunos(List<String> jaNaTurma) async {
    final selecionados = await Navigator.of(context).push<List<Perfil>>(
      MaterialPageRoute(
        builder: (_) => SelecionarUsuariosScreen(
          titulo: 'Adicionar alunos',
          role: 'aluno',
          jaAdicionados: jaNaTurma.toSet(),
        ),
      ),
    );
    if (selecionados == null || selecionados.isEmpty) return;

    try {
      await TurmasService.adicionarAlunos(
        widget.turma.id,
        selecionados.map((p) => p.id).toList(),
      );
      _mudou = true;
      if (mounted) {
        mostrarOk(context, '${selecionados.length} aluno(s) adicionado(s)');
        _recarregar();
      }
    } catch (e) {
      if (mounted) mostrarErro(context, e);
    }
  }

  Future<void> _removerAluno(AlunoFrequencia aluno) async {
    final confirmado = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Remover aluno?'),
        content: Text('${aluno.nome} sai da turma "${widget.turma.nome}".'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Remover'),
          ),
        ],
      ),
    );
    if (confirmado != true) return;

    try {
      await TurmasService.removerAluno(widget.turma.id, aluno.id);
      _mudou = true;
      if (mounted) {
        mostrarOk(context, 'Aluno removido');
        _recarregar();
      }
    } catch (e) {
      if (mounted) mostrarErro(context, e);
    }
  }

  @override
  Widget build(BuildContext context) {
    final ehProfessor = context.watch<AuthProvider>().perfil?.isProfessor ?? false;

    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) {
        if (!didPop) Navigator.of(context).pop(_mudou);
      },
      child: Scaffold(
        appBar: AppBar(
          title: Text(widget.turma.nome),
          actions: ehProfessor
              ? [
                  IconButton(
                    icon: const Icon(Icons.event_repeat),
                    tooltip: 'Nova aula recorrente',
                    onPressed: () async {
                      final criou = await Navigator.of(context).push<bool>(
                        MaterialPageRoute(
                          builder: (_) => CriarRecorrenciaScreen(turma: widget.turma),
                        ),
                      );
                      if (criou == true) _mudou = true;
                    },
                  ),
                ]
              : null,
        ),
        // Carrega pela rota de frequência (e não pela de alunos) porque ela
        // já devolve nome/matrícula junto com a presença - uma requisição só.
        body: ListaAsync<AlunoFrequencia>(
          key: ValueKey(_versao),
          carregar: () => TurmasService.frequencia(widget.turma.id),
          mensagemVazia: 'Nenhum aluno nessa turma ainda',
          iconeVazio: Icons.person_off_outlined,
          reservarEspacoFab: ehProfessor,
          itemBuilder: (context, aluno) => ListTile(
            leading: CircleAvatar(child: Text(_iniciais(aluno.nome))),
            title: Text(aluno.nome),
            subtitle: Text(
              [
                if (aluno.matricula != null && aluno.matricula!.isNotEmpty)
                  aluno.matricula!,
                // Só a sigla: "Engenharia de Telecomunicações" por extenso
                // não cabe na linha e empurra a frequência pra fora.
                if (aluno.curso != null) _sigla(aluno.curso!),
                aluno.frequencia.semAulas
                    ? 'sem aulas ainda'
                    : '${aluno.frequencia.presencas}/${aluno.frequencia.total} aulas',
                // O que o professor consegue usar: não "está com 62%", mas
                // "ainda pode faltar 1". É o aviso que chega a tempo de a
                // conversa com o aluno resolver alguma coisa.
                if (aluno.frequencia.reprovadoPorFalta)
                  'passou do limite'
                else if (aluno.frequencia.noLimite)
                  'pode faltar ${aluno.frequencia.faltasRestantes}',
              ].join(' · '),
              style: Tipos.dado(context),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                _SeloFrequencia(frequencia: aluno.frequencia),
                if (ehProfessor)
                  IconButton(
                    icon: const Icon(Icons.remove_circle_outline),
                    tooltip: 'Remover',
                    onPressed: () => _removerAluno(aluno),
                  ),
              ],
            ),
          ),
        ),
        floatingActionButton: ehProfessor
            ? FloatingActionButton.extended(
                onPressed: () async {
                  final atuais = await TurmasService.listarAlunos(widget.turma.id);
                  _adicionarAlunos(atuais.map((a) => a.id).toList());
                },
                icon: const Icon(Icons.person_add),
                label: const Text('Adicionar alunos'),
              )
            : null,
      ),
    );
  }
}

/// Percentual de presença do aluno, com a cor dizendo se está em risco.
/// 75% é o piso acadêmico usual pra aprovação por frequência.
///
/// Quem já passou do limite de faltas ganha um ponto ao lado: o percentual
/// sozinho não distingue "62% em fevereiro, ainda dá pra recuperar" de "62%
/// e não cabe mais falta nenhuma", e essas duas situações pedem conversas
/// diferentes.
class _SeloFrequencia extends StatelessWidget {
  final Frequencia frequencia;

  const _SeloFrequencia({required this.frequencia});

  @override
  Widget build(BuildContext context) {
    if (frequencia.semAulas) return const SizedBox.shrink();

    final pct = frequencia.percentual ?? 0;
    final selo = Selo(texto: '$pct%', cor: corDaFrequencia(context, pct));
    if (!frequencia.reprovadoPorFalta) return selo;

    return Row(mainAxisSize: MainAxisSize.min, children: [
      Icon(Icons.error, size: 13, color: CoresStatus.erro(context)),
      const SizedBox(width: 5),
      selo,
    ]);
  }
}

/// "Engenharia de Computação" -> "COMPUTAÇÃO". O servidor manda o nome por
/// extenso porque é o dado correto; a lista é que não tem largura pra ele.
String _sigla(String curso) {
  final ultima = curso.split(' ').last;
  return ultima.toUpperCase();
}

String _iniciais(String nome) {
  final partes = nome.trim().split(RegExp(r'\s+'));
  final letras = partes.take(2).map((p) => p.isEmpty ? '' : p[0]).join();
  return letras.toUpperCase();
}
