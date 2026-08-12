import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config/tema.dart';
import '../models/turma.dart';
import '../services/auth_provider.dart';
import '../services/turmas_service.dart';
import '../widgets/lista_async.dart';
import 'turma_detail_screen.dart';

class TurmasScreen extends StatefulWidget {
  const TurmasScreen({super.key});

  @override
  State<TurmasScreen> createState() => _TurmasScreenState();
}

class _TurmasScreenState extends State<TurmasScreen> {
  int _versao = 0;

  void _recarregar() => setState(() => _versao++);

  Future<void> _criarTurma() async {
    final nome = await showDialog<String>(
      context: context,
      builder: (_) => const _DialogNovaTurma(),
    );
    if (nome == null || nome.trim().isEmpty) return;

    try {
      await TurmasService.criar(nome.trim());
      if (mounted) {
        mostrarOk(context, 'Turma criada');
        _recarregar();
      }
    } catch (e) {
      if (mounted) mostrarErro(context, e);
    }
  }

  @override
  Widget build(BuildContext context) {
    final ehProfessor = context.watch<AuthProvider>().perfil?.isProfessor ?? false;

    // Sem AppBar: é aba da HomeScreen, que já tem a sua. Ver eventos_screen.
    return Scaffold(
      body: ListaAsync<Turma>(
        key: ValueKey(_versao),
        carregar: TurmasService.listar,
        mensagemVazia: ehProfessor
            ? 'Você ainda não criou nenhuma turma'
            : 'Você ainda não está em nenhuma turma',
        iconeVazio: Icons.groups_outlined,
        reservarEspacoFab: ehProfessor,
        itemBuilder: (context, t) => InkWell(
          onTap: () async {
            final mudou = await Navigator.of(context).push<bool>(
              MaterialPageRoute(
                builder: (_) => TurmaDetailScreen(turma: t),
              ),
            );
            if (mudou == true) _recarregar();
          },
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 15, 12, 15),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        t.nome,
                        style: const TextStyle(
                          fontSize: 15.5,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                      if (ehProfessor && t.totalAlunos != null) ...[
                        const SizedBox(height: 4),
                        // Contagem é registro do sistema, não algo que o
                        // professor digitou - por isso mono, igual à
                        // matrícula e ao horário de entrada nas outras telas.
                        Text(
                          '${t.totalAlunos} aluno${t.totalAlunos == 1 ? '' : 's'}',
                          style: Tipos.dado(context),
                        ),
                      ],
                    ],
                  ),
                ),
                Icon(
                  Icons.chevron_right,
                  size: 20,
                  color: Theme.of(context).colorScheme.outline,
                ),
              ],
            ),
          ),
        ),
      ),
      floatingActionButton: ehProfessor
          ? FloatingActionButton.extended(
              onPressed: _criarTurma,
              icon: const Icon(Icons.add),
              label: const Text('Nova turma'),
            )
          : null,
    );
  }
}

class _DialogNovaTurma extends StatefulWidget {
  const _DialogNovaTurma();

  @override
  State<_DialogNovaTurma> createState() => _DialogNovaTurmaState();
}

class _DialogNovaTurmaState extends State<_DialogNovaTurma> {
  final _ctrl = TextEditingController();

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Nova turma'),
      content: TextField(
        controller: _ctrl,
        autofocus: true,
        decoration: const InputDecoration(labelText: 'Nome da turma'),
        onSubmitted: (v) => Navigator.pop(context, v),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancelar'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context, _ctrl.text),
          child: const Text('Criar'),
        ),
      ],
    );
  }
}
