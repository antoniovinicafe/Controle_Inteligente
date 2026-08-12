import 'package:flutter/material.dart';

import '../config/tema.dart';
import '../models/evento.dart';
import '../services/eventos_service.dart';
import '../utils/formatters.dart';
import '../widgets/lista_async.dart';

/// Serve pra criar e pra editar - os campos são os mesmos, só muda o que
/// acontece no salvar. Passe [evento] pra abrir em modo edição.
class CriarEventoScreen extends StatefulWidget {
  final Evento? evento;

  const CriarEventoScreen({super.key, this.evento});

  @override
  State<CriarEventoScreen> createState() => _CriarEventoScreenState();
}

class _CriarEventoScreenState extends State<CriarEventoScreen> {
  final _formKey = GlobalKey<FormState>();
  final _tituloCtrl = TextEditingController();
  final _descricaoCtrl = TextEditingController();
  final _localCtrl = TextEditingController();
  final _capacidadeCtrl = TextEditingController();

  DateTime? _inicio;
  DateTime? _fim;
  bool _salvando = false;

  bool get _editando => widget.evento != null;

  @override
  void initState() {
    super.initState();
    final e = widget.evento;
    if (e == null) return;
    _tituloCtrl.text = e.titulo;
    _descricaoCtrl.text = e.descricao ?? '';
    _localCtrl.text = e.local ?? '';
    _capacidadeCtrl.text = e.capacidade?.toString() ?? '';
    _inicio = e.dataInicio;
    _fim = e.dataFim;
  }

  @override
  void dispose() {
    _tituloCtrl.dispose();
    _descricaoCtrl.dispose();
    _localCtrl.dispose();
    _capacidadeCtrl.dispose();
    super.dispose();
  }

  Future<DateTime?> _escolherDataHora(DateTime? inicial) async {
    final base = inicial ?? DateTime.now();
    // Ao editar um evento que já passou, o limite "ontem" deixaria a data
    // atual dele fora do calendário - então o piso acompanha o valor atual.
    var piso = DateTime.now().subtract(const Duration(days: 1));
    if (base.isBefore(piso)) piso = base;
    final data = await showDatePicker(
      context: context,
      initialDate: base,
      firstDate: piso,
      lastDate: DateTime.now().add(const Duration(days: 730)),
    );
    if (data == null || !mounted) return null;

    final hora = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(base),
    );
    if (hora == null) return null;

    return DateTime(data.year, data.month, data.day, hora.hour, hora.minute);
  }

  Future<void> _selecionarInicio() async {
    final v = await _escolherDataHora(_inicio);
    if (v == null) return;
    setState(() {
      _inicio = v;
      // Empurra o fim junto se ele ficou antes do novo início.
      if (_fim != null && !_fim!.isAfter(v)) {
        _fim = v.add(const Duration(hours: 1));
      }
    });
  }

  Future<void> _selecionarFim() async {
    final v = await _escolherDataHora(_fim ?? _inicio?.add(const Duration(hours: 1)));
    if (v == null) return;
    setState(() => _fim = v);
  }

  Future<void> _salvar() async {
    if (!_formKey.currentState!.validate()) return;
    if (_inicio == null || _fim == null) {
      mostrarErro(context, 'Escolha data/hora de início e fim');
      return;
    }
    if (!_fim!.isAfter(_inicio!)) {
      mostrarErro(context, 'O fim precisa ser depois do início');
      return;
    }

    setState(() => _salvando = true);
    final titulo = _tituloCtrl.text.trim();
    final descricao = _descricaoCtrl.text.trim();
    final local = _localCtrl.text.trim();
    final capacidade = _capacidadeCtrl.text.trim().isEmpty
        ? null
        : int.tryParse(_capacidadeCtrl.text.trim());
    try {
      if (_editando) {
        await EventosService.editar(widget.evento!.id, {
          'titulo': titulo,
          'descricao': descricao.isEmpty ? null : descricao,
          'local': local.isEmpty ? null : local,
          // Mesmo cuidado do criar: manda em UTC com 'Z', senão o
          // timestamptz do Postgres interpreta errado.
          'data_inicio': _inicio!.toUtc().toIso8601String(),
          'data_fim': _fim!.toUtc().toIso8601String(),
          'capacidade': capacidade,
        });
      } else {
        await EventosService.criar(
          titulo: titulo,
          descricao: descricao.isEmpty ? null : descricao,
          local: local.isEmpty ? null : local,
          dataInicio: _inicio!,
          dataFim: _fim!,
          capacidade: capacidade,
        );
      }
      if (mounted) Navigator.pop(context, true);
    } catch (e) {
      if (mounted) mostrarErro(context, e);
    } finally {
      if (mounted) setState(() => _salvando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(_editando ? 'Editar evento' : 'Novo evento')),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
          children: [
            // Três blocos em vez de uma pilha de oito campos iguais. A
            // divisão não é enfeite: é a ordem em que a pessoa decide as
            // coisas - primeiro o que é a aula, depois quando ela acontece,
            // e por último o limite (que quase sempre fica vazio).
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
              maxLines: 3,
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
            const _Secao('QUANDO'),
            _CampoData(label: 'Início', valor: _inicio, onTap: _selecionarInicio),
            const SizedBox(height: 12),
            _CampoData(label: 'Fim', valor: _fim, onTap: _selecionarFim),
            const _Secao('QUANTAS PESSOAS'),
            TextFormField(
              controller: _capacidadeCtrl,
              decoration: const InputDecoration(
                labelText: 'Capacidade (opcional)',
                hintText: 'Em branco = sem limite',
              ),
              keyboardType: TextInputType.number,
            ),
            const SizedBox(height: 32),
            FilledButton(
              onPressed: _salvando ? null : _salvar,
              child: _salvando
                  ? const SizedBox(
                      height: 20,
                      width: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : Text(_editando ? 'Salvar alterações' : 'Criar evento'),
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

class _CampoData extends StatelessWidget {
  final String label;
  final DateTime? valor;
  final VoidCallback onTap;

  const _CampoData({required this.label, required this.valor, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final cores = Theme.of(context).colorScheme;
    final vazio = valor == null;

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: InputDecorator(
        // Sem `border:` aqui - o OutlineInputBorder cru que estava neste
        // ponto ignorava o inputDecorationTheme e deixava os dois campos de
        // data com uma moldura diferente da dos campos de texto logo acima.
        decoration: InputDecoration(
          labelText: label,
          suffixIcon: Icon(Icons.calendar_today_outlined, size: 18, color: cores.outline),
        ),
        child: Text(
          vazio ? 'Selecionar' : formatarDataHora(valor!),
          // Data escolhida vira carimbo do sistema, e é assim que ela
          // reaparece na lista de eventos - mesma voz nos dois lugares.
          style: vazio
              ? TextStyle(color: cores.onSurfaceVariant)
              : Tipos.dado(context, tamanho: 13.5, cor: cores.onSurface),
        ),
      ),
    );
  }
}
