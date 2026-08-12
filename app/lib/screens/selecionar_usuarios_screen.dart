import 'dart:async';

import 'package:flutter/material.dart';

import '../config/tema.dart';
import '../models/perfil.dart';
import '../services/usuarios_service.dart';
import '../widgets/lista_async.dart';

/// Busca + seleção múltipla de usuários. Devolve via Navigator.pop
/// a lista de selecionados (ou null se cancelar).
///
/// Usada tanto pra "adicionar alunos na turma" quanto pra
/// "convidar participantes pro evento".
class SelecionarUsuariosScreen extends StatefulWidget {
  final String titulo;

  /// Filtra por papel (ex: 'aluno' ao montar turma). null = todos.
  final String? role;

  /// Ids que já estão na turma/evento - aparecem marcados e desabilitados.
  final Set<String> jaAdicionados;

  const SelecionarUsuariosScreen({
    super.key,
    required this.titulo,
    this.role,
    this.jaAdicionados = const {},
  });

  @override
  State<SelecionarUsuariosScreen> createState() =>
      _SelecionarUsuariosScreenState();
}

class _SelecionarUsuariosScreenState extends State<SelecionarUsuariosScreen> {
  final _buscaCtrl = TextEditingController();
  final _selecionados = <String, Perfil>{};
  Timer? _debounce;
  int _versao = 0;

  Future<List<Perfil>> _buscar() =>
      UsuariosService.buscar(busca: _buscaCtrl.text, role: widget.role);

  /// Espera o usuário parar de digitar antes de bater na API.
  void _onBuscaMudou(String _) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 400), () {
      setState(() => _versao++);
    });
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _buscaCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.titulo),
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(64),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
            child: TextField(
              controller: _buscaCtrl,
              onChanged: _onBuscaMudou,
              decoration: const InputDecoration(
                hintText: 'Buscar por nome ou matrícula',
                prefixIcon: Icon(Icons.search),
                border: OutlineInputBorder(),
                isDense: true,
              ),
            ),
          ),
        ),
      ),
      body: ListaAsync<Perfil>(
        key: ValueKey(_versao),
        carregar: _buscar,
        mensagemVazia: 'Nenhum usuário encontrado',
        iconeVazio: Icons.person_search,
        reservarEspacoFab: true,
        itemBuilder: (context, p) {
          final jaTem = widget.jaAdicionados.contains(p.id);
          final marcado = jaTem || _selecionados.containsKey(p.id);

          return CheckboxListTile(
            value: marcado,
            // Quem já está na lista não pode ser desmarcado aqui.
            onChanged: jaTem
                ? null
                : (v) => setState(() {
                      if (v == true) {
                        _selecionados[p.id] = p;
                      } else {
                        _selecionados.remove(p.id);
                      }
                    }),
            title: Text(p.nome),
            subtitle: Text(
              [
                if (p.matricula != null && p.matricula!.isNotEmpty) p.matricula!,
                if (jaTem) 'já adicionado' else p.role,
              ].join(' · '),
              style: Tipos.dado(context),
            ),
            secondary: CircleAvatar(
              child: Text(_iniciais(p.nome)),
            ),
          );
        },
      ),
      floatingActionButton: _selecionados.isEmpty
          ? null
          : FloatingActionButton.extended(
              onPressed: () =>
                  Navigator.pop(context, _selecionados.values.toList()),
              icon: const Icon(Icons.check),
              label: Text('Adicionar (${_selecionados.length})'),
            ),
    );
  }
}

String _iniciais(String nome) {
  final partes = nome.trim().split(RegExp(r'\s+'));
  final letras = partes.take(2).map((p) => p.isEmpty ? '' : p[0]).join();
  return letras.toUpperCase();
}
