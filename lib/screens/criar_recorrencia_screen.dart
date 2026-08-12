import 'package:flutter/material.dart';

import '../config/tema.dart';
import '../models/recorrencia.dart';
import '../models/turma.dart';
import '../services/recorrencias_service.dart';
import '../widgets/lista_async.dart';

/// Cria uma aula recorrente pra uma turma ("toda X e Y, tal horário,
/// entre tal e tal data"). O backend expande isso em um evento de
/// verdade por ocorrência - essa tela só monta a regra.
class CriarRecorrenciaScreen extends StatefulWidget {
  final Turma turma;

  const CriarRecorrenciaScreen({super.key, required this.turma});

  @override
  State<CriarRecorrenciaScreen> createState() => _CriarRecorrenciaScreenState();
}

class _CriarRecorrenciaScreenState extends State<CriarRecorrenciaScreen> {
  final _formKey = GlobalKey<FormState>();
  final _tituloCtrl = TextEditingController();
  final _descricaoCtrl = TextEditingController();
  final _localCtrl = TextEditingController();
  final _capacidadeCtrl = TextEditingController();

  final Set<int> _diasSelecionados = {};
  TimeOfDay? _horaInicio;
  TimeOfDay? _horaFim;
  DateTime? _dataInicio;
  DateTime? _dataFim;
  bool _salvando = false;

  @override
  void dispose() {
    _tituloCtrl.dispose();
    _descricaoCtrl.dispose();
    _localCtrl.dispose();
    _capacidadeCtrl.dispose();
    super.dispose();
  }

  Future<void> _escolherHora(bool inicio) async {
    final hora = await showTimePicker(
      context: context,
      initialTime: (inicio ? _horaInicio : _horaFim) ?? TimeOfDay.now(),
    );
    if (hora == null) return;
    setState(() {
      if (inicio) {
        _horaInicio = hora;
      } else {
        _horaFim = hora;
      }
    });
  }

  Future<void> _escolherData(bool inicio) async {
    final base = (inicio ? _dataInicio : _dataFim) ?? DateTime.now();
    final data = await showDatePicker(
      context: context,
      initialDate: base,
      firstDate: DateTime.now().subtract(const Duration(days: 1)),
      lastDate: DateTime.now().add(const Duration(days: 366)),
    );
    if (data == null) return;
    setState(() {
      if (inicio) {
        _dataInicio = data;
        if (_dataFim != null && _dataFim!.isBefore(data)) _dataFim = data;
      } else {
        _dataFim = data;
      }
    });
  }

  Future<void> _salvar() async {
    if (!_formKey.currentState!.validate()) return;
    if (_diasSelecionados.isEmpty) {
      mostrarErro(context, 'Escolha pelo menos um dia da semana');
      return;
    }
    if (_horaInicio == null || _horaFim == null) {
      mostrarErro(context, 'Escolha o horário de início e fim');
      return;
    }
    if (_dataInicio == null || _dataFim == null) {
      mostrarErro(context, 'Escolha o período (data de início e fim)');
      return;
    }
    final inicioMin = _horaInicio!.hour * 60 + _horaInicio!.minute;
    final fimMin = _horaFim!.hour * 60 + _horaFim!.minute;
    if (fimMin <= inicioMin) {
      mostrarErro(context, 'O horário de fim precisa ser depois do início');
      return;
    }

    setState(() => _salvando = true);
    try {
      final resultado = await RecorrenciasService.criar(
        turmaId: widget.turma.id,
        titulo: _tituloCtrl.text.trim(),
        descricao: _descricaoCtrl.text.trim().isEmpty ? null : _descricaoCtrl.text.trim(),
        local: _localCtrl.text.trim().isEmpty ? null : _localCtrl.text.trim(),
        capacidade: _capacidadeCtrl.text.trim().isEmpty
            ? null
            : int.tryParse(_capacidadeCtrl.text.trim()),
        diasSemana: _diasSelecionados.toList()..sort(),
        horaInicio: _formatarHora(_horaInicio!),
        horaFim: _formatarHora(_horaFim!),
        dataInicio: _dataInicio!,
        dataFim: _dataFim!,
      );
      if (mounted) {
        final total = resultado['total_eventos'];
        mostrarOk(context, '$total aula(s) criada(s)');
        Navigator.pop(context, true);
      }
    } catch (e) {
      if (mounted) mostrarErro(context, e);
    } finally {
      if (mounted) setState(() => _salvando = false);
    }
  }

  /// Quantas aulas serão criadas com a regra montada até agora, ou null
  /// enquanto faltar informação pra saber. A conta em si mora no model,
  /// junto do backend que ela espelha.
  int? get _quantasAulas {
    if (_diasSelecionados.isEmpty || _dataInicio == null || _dataFim == null) {
      return null;
    }
    return contarOcorrencias(_diasSelecionados, _dataInicio!, _dataFim!);
  }

  String _formatarHora(TimeOfDay t) =>
      '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';

  String _formatarData(DateTime d) =>
      '${d.day.toString().padLeft(2, '0')}/${d.month.toString().padLeft(2, '0')}/${d.year}';

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Aula recorrente · ${widget.turma.nome}')),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
          children: [
            const _Secao('O QUE É'),
            TextFormField(
              controller: _tituloCtrl,
              textCapitalization: TextCapitalization.sentences,
              decoration: const InputDecoration(labelText: 'Título'),
              validator: (v) => (v == null || v.trim().isEmpty) ? 'Obrigatório' : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _descricaoCtrl,
              textCapitalization: TextCapitalization.sentences,
              decoration: const InputDecoration(labelText: 'Descrição (opcional)'),
              maxLines: 2,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _localCtrl,
              textCapitalization: TextCapitalization.words,
              decoration: const InputDecoration(
                labelText: 'Local (opcional)',
                hintText: 'Sala, laboratório, bloco',
              ),
            ),
            const _Secao('EM QUAIS DIAS'),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: nomesDiasSemana.entries.map((e) {
                final marcado = _diasSelecionados.contains(e.key);
                return FilterChip(
                  label: Text(e.value),
                  selected: marcado,
                  onSelected: (v) => setState(() {
                    if (v) {
                      _diasSelecionados.add(e.key);
                    } else {
                      _diasSelecionados.remove(e.key);
                    }
                  }),
                );
              }).toList(),
            ),
            const _Secao('EM QUE HORÁRIO'),
            Row(
              children: [
                Expanded(
                  child: _CampoEscolha(
                    label: 'Começa',
                    valor: _horaInicio == null ? 'Selecionar' : _formatarHora(_horaInicio!),
                    icone: Icons.access_time,
                    onTap: () => _escolherHora(true),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _CampoEscolha(
                    label: 'Termina',
                    valor: _horaFim == null ? 'Selecionar' : _formatarHora(_horaFim!),
                    icone: Icons.access_time,
                    onTap: () => _escolherHora(false),
                  ),
                ),
              ],
            ),
            const _Secao('DE QUANDO ATÉ QUANDO'),
            Row(
              children: [
                Expanded(
                  child: _CampoEscolha(
                    label: 'De',
                    valor: _dataInicio == null ? 'Selecionar' : _formatarData(_dataInicio!),
                    icone: Icons.calendar_today,
                    onTap: () => _escolherData(true),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _CampoEscolha(
                    label: 'Até',
                    valor: _dataFim == null ? 'Selecionar' : _formatarData(_dataFim!),
                    icone: Icons.calendar_today,
                    onTap: () => _escolherData(false),
                  ),
                ),
              ],
            ),
            const _Secao('QUANTAS PESSOAS'),
            TextFormField(
              controller: _capacidadeCtrl,
              decoration: const InputDecoration(
                labelText: 'Capacidade (opcional)',
                hintText: 'Em branco = sem limite',
              ),
              keyboardType: TextInputType.number,
            ),
            const SizedBox(height: 28),
            _Previsao(
              quantas: _quantasAulas,
              turma: widget.turma.nome,
            ),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: _salvando ? null : _salvar,
              child: _salvando
                  ? const SizedBox(
                      height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('Criar aulas'),
            ),
          ],
        ),
      ),
    );
  }
}

/// Régua entre blocos do formulário.
class _Secao extends StatelessWidget {
  final String texto;

  const _Secao(this.texto);

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(top: 28, bottom: 10),
        child: Text(texto, style: Tipos.etiqueta(context)),
      );
}

/// Quantas aulas o botão vai criar de verdade.
///
/// Esta tela cria N eventos de uma vez, e desfazer isso depois é ir de um
/// em um. Dizer o número antes do toque é a diferença entre uma ação
/// reversível na cabeça da pessoa e uma surpresa.
class _Previsao extends StatelessWidget {
  final int? quantas;
  final String turma;

  const _Previsao({required this.quantas, required this.turma});

  @override
  Widget build(BuildContext context) {
    final cores = Theme.of(context).colorScheme;
    final pronto = quantas != null && quantas! > 0;

    return Container(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 15),
      decoration: BoxDecoration(
        color: cores.surfaceContainerHighest.withValues(
          alpha: Theme.of(context).brightness == Brightness.dark ? 0.35 : 0.7,
        ),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('VAI CRIAR', style: Tipos.etiqueta(context)),
          const SizedBox(height: 8),
          if (!pronto)
            Text(
              quantas == 0
                  ? 'Nenhuma aula cai nesse intervalo. Confira os dias e as datas.'
                  : 'Escolha os dias da semana e o período.',
              style: TextStyle(color: cores.onSurfaceVariant, fontSize: 13.5, height: 1.4),
            )
          else ...[
            Row(
              crossAxisAlignment: CrossAxisAlignment.baseline,
              textBaseline: TextBaseline.alphabetic,
              children: [
                Text(
                  '$quantas',
                  style: Tipos.numeral(context, cor: cores.primary, tamanho: 30),
                ),
                const SizedBox(width: 8),
                Text(
                  quantas == 1 ? 'aula' : 'aulas',
                  style: TextStyle(fontSize: 15, color: cores.onSurface),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              'A turma "$turma" inteira é convidada em cada uma.',
              style: TextStyle(color: cores.outline, fontSize: 12.5, height: 1.35),
            ),
          ],
        ],
      ),
    );
  }
}

class _CampoEscolha extends StatelessWidget {
  final String label;
  final String valor;
  final IconData icone;
  final VoidCallback onTap;

  const _CampoEscolha({
    required this.label,
    required this.valor,
    required this.icone,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final cores = Theme.of(context).colorScheme;
    final vazio = valor == 'Selecionar';

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: InputDecorator(
        // Sem `border:` cru - deixava estes campos com moldura diferente da
        // dos campos de texto da mesma tela.
        decoration: InputDecoration(
          labelText: label,
          isDense: true,
          suffixIcon: Icon(icone, size: 17, color: cores.outline),
          suffixIconConstraints: const BoxConstraints(minWidth: 38),
        ),
        child: Text(
          valor,
          style: vazio
              ? TextStyle(color: cores.onSurfaceVariant, fontSize: 13.5)
              : Tipos.dado(context, tamanho: 13.5, cor: cores.onSurface),
        ),
      ),
    );
  }
}
