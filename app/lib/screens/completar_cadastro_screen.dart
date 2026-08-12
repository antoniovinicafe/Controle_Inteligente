import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config/tema.dart';
import '../services/auth_provider.dart';
import 'configuracoes_screen.dart';

class CompletarCadastroScreen extends StatefulWidget {
  const CompletarCadastroScreen({super.key});

  @override
  State<CompletarCadastroScreen> createState() => _CompletarCadastroScreenState();
}

class _CompletarCadastroScreenState extends State<CompletarCadastroScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nomeCtrl = TextEditingController();
  final _matriculaCtrl = TextEditingController();
  String _role = 'aluno';
  bool _carregando = false;

  Future<void> _salvar() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _carregando = true);
    try {
      await context.read<AuthProvider>().completarCadastro(
            nome: _nomeCtrl.text.trim(),
            matricula: _matriculaCtrl.text.trim(),
            role: _role,
          );
      // Provider já atualiza o status pra 'logado' -> a navegação
      // principal (main.dart) troca de tela automaticamente
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('Erro ao salvar: $e'),
          backgroundColor: CoresStatus.erro(context),
        ));
      }
    } finally {
      if (mounted) setState(() => _carregando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Complete seu cadastro'),
        // Esta tela é a única que exige o servidor antes do app abrir.
        // Sem este atalho, um endereço errado prende a pessoa aqui sem
        // nenhum caminho pra consertar.
        actions: [
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            tooltip: 'Ajustes',
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const ConfiguracoesScreen()),
            ),
          ),
        ],
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  'Esses dados aparecem na lista de presença das aulas.',
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                    height: 1.4,
                  ),
                ),
                const SizedBox(height: 26),
                TextFormField(
                  controller: _nomeCtrl,
                  textCapitalization: TextCapitalization.words,
                  decoration: const InputDecoration(labelText: 'Nome completo'),
                  validator: (v) => (v == null || v.trim().isEmpty) ? 'Obrigatório' : null,
                ),
                const SizedBox(height: 14),
                TextFormField(
                  controller: _matriculaCtrl,
                  decoration: const InputDecoration(labelText: 'Matrícula'),
                  validator: (v) => (v == null || v.trim().isEmpty) ? 'Obrigatório' : null,
                ),
                const SizedBox(height: 30),
                // Escolher aqui muda o app que a pessoa recebe (professor
                // ganha a aba Turmas e pode criar aula), então isso não pode
                // continuar sendo um dropdown fechado que esconde as opções
                // e o que cada uma significa.
                Text('VOCÊ É', style: Tipos.etiqueta(context)),
                const SizedBox(height: 10),
                SegmentedButton<String>(
                  segments: const [
                    ButtonSegment(value: 'aluno', label: Text('Aluno')),
                    ButtonSegment(value: 'professor', label: Text('Professor')),
                  ],
                  selected: {_role},
                  showSelectedIcon: false,
                  onSelectionChanged: (s) => setState(() => _role = s.first),
                ),
                const SizedBox(height: 10),
                Text(
                  _role == 'professor'
                      ? 'Cria turmas e aulas, e acompanha quem entrou em cada uma.'
                      : 'Participa das aulas e vê a própria presença.',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Theme.of(context).colorScheme.outline,
                        height: 1.4,
                      ),
                ),
                const SizedBox(height: 34),
                FilledButton(
                  onPressed: _carregando ? null : _salvar,
                  child: _carregando
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Concluir cadastro'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
