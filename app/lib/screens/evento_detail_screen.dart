import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config/tema.dart';
import '../models/access_log.dart';
import '../models/evento.dart';
import '../models/participante.dart';
import '../models/perfil.dart';
import '../models/turma.dart';
import '../services/api_client.dart';
import '../services/auth_provider.dart';
import '../services/eventos_service.dart';
import '../services/recorrencias_service.dart';
import '../services/turmas_service.dart';
import '../utils/formatters.dart';
import '../widgets/lista_async.dart';
import 'criar_evento_screen.dart';
import 'eventos_screen.dart' show Selo;
import 'selecionar_usuarios_screen.dart';

class EventoDetailScreen extends StatefulWidget {
  final int eventoId;

  const EventoDetailScreen({super.key, required this.eventoId});

  @override
  State<EventoDetailScreen> createState() => _EventoDetailScreenState();
}

class _EventoDetailScreenState extends State<EventoDetailScreen> {
  // Muda a cada ação que precisa recarregar os dados do zero. Usado como
  // key do corpo pra forçar remontagem completa em vez de depender de
  // FutureBuilder detectar um Future reatribuído sozinho (ver lista_async.dart).
  int _versao = 0;
  bool _mudou = false;

  void _recarregar() => setState(() => _versao++);

  @override
  Widget build(BuildContext context) {
    final perfil = context.watch<AuthProvider>().perfil;
    final ehProfessor = perfil?.isProfessor ?? false;

    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) {
        if (!didPop) Navigator.of(context).pop(_mudou);
      },
      child: DefaultTabController(
        length: ehProfessor ? 2 : 1,
        child: _EventoCorpo(
          key: ValueKey(_versao),
          eventoId: widget.eventoId,
          ehProfessor: ehProfessor,
          meuId: perfil?.id,
          onMudou: () => _mudou = true,
          onRecarregar: _recarregar,
        ),
      ),
    );
  }
}

/// Todo o conteúdo que depende de dados carregados da API. Isolado num
/// widget próprio, remontado via troca de `key` sempre que algo muda -
/// evita a classe de bug onde reatribuir um Future guardado em campo de
/// State não é percebido por um FutureBuilder mais acima.
class _EventoCorpo extends StatefulWidget {
  final int eventoId;
  final bool ehProfessor;
  final String? meuId;
  final VoidCallback onMudou;
  final VoidCallback onRecarregar;

  const _EventoCorpo({
    required super.key,
    required this.eventoId,
    required this.ehProfessor,
    required this.meuId,
    required this.onMudou,
    required this.onRecarregar,
  });

  @override
  State<_EventoCorpo> createState() => _EventoCorpoState();
}

class _EventoCorpoState extends State<_EventoCorpo> {
  late final Future<Evento> _futureEvento;

  @override
  void initState() {
    super.initState();
    _futureEvento = EventosService.detalhe(widget.eventoId);
  }

  void _recarregar() {
    widget.onMudou();
    widget.onRecarregar();
  }

  Future<void> _mudarStatus(String status) async {
    try {
      await EventosService.alterarStatus(widget.eventoId, status);
      if (mounted) _recarregar();
    } catch (e) {
      if (mounted) mostrarErro(context, e);
    }
  }

  Future<void> _cancelar() async {
    final confirmado = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Cancelar evento?'),
        content: const Text('Os participantes convidados continuam na lista, mas o evento fica marcado como cancelado.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Voltar')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Cancelar evento')),
        ],
      ),
    );
    if (confirmado != true) return;
    try {
      await EventosService.cancelar(widget.eventoId);
      if (mounted) _recarregar();
    } catch (e) {
      if (mounted) mostrarErro(context, e);
    }
  }

  Future<void> _cancelarSerie(int recorrenciaId) async {
    final confirmado = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Cancelar a série toda?'),
        content: const Text(
          'Cancela essa e todas as próximas aulas dessa recorrência que ainda não aconteceram. '
          'As que já aconteceram (ou já foram individualmente canceladas) não são afetadas.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Voltar')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Cancelar série')),
        ],
      ),
    );
    if (confirmado != true) return;
    try {
      final total = await RecorrenciasService.cancelar(recorrenciaId);
      if (mounted) {
        mostrarOk(context, '$total aula(s) futura(s) cancelada(s)');
        _recarregar();
      }
    } catch (e) {
      if (mounted) mostrarErro(context, e);
    }
  }

  Future<void> _excluir() async {
    final confirmado = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Excluir evento?'),
        content: const Text(
          'Apaga o evento e a lista de participantes de vez - isso não pode ser desfeito. '
          'Só funciona se ninguém tiver sido liberado nele ainda; se já teve acesso registrado, cancele em vez de excluir.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Voltar')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: CoresStatus.erro(context)),
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Excluir'),
          ),
        ],
      ),
    );
    if (confirmado != true) return;
    try {
      await EventosService.excluir(widget.eventoId);
      if (mounted) {
        mostrarOk(context, 'Evento excluído');
        widget.onMudou();
        Navigator.of(context).pop(true);
      }
    } catch (e) {
      if (mounted) mostrarErro(context, e);
    }
  }

  Future<void> _liberar(Participante p) async {
    try {
      await EventosService.liberar(widget.eventoId, p.usuarioId);
      if (mounted) {
        mostrarOk(context, '${p.nome} liberado');
        _recarregar();
      }
    } catch (e) {
      if (mounted) mostrarErro(context, e);
    }
  }

  Future<void> _removerParticipante(Participante p) async {
    try {
      await EventosService.removerParticipante(widget.eventoId, p.usuarioId);
      if (mounted) {
        mostrarOk(context, '${p.nome} removido');
        _recarregar();
      }
    } catch (e) {
      if (mounted) mostrarErro(context, e);
    }
  }

  Future<void> _convidarAlunos(List<String> jaConvidados) async {
    final selecionados = await Navigator.of(context).push<List<Perfil>>(
      MaterialPageRoute(
        builder: (_) => SelecionarUsuariosScreen(
          titulo: 'Convidar participantes',
          jaAdicionados: jaConvidados.toSet(),
        ),
      ),
    );
    if (selecionados == null || selecionados.isEmpty) return;

    try {
      await EventosService.convidar(
        widget.eventoId,
        usuarioIds: selecionados.map((p) => p.id).toList(),
      );
      if (mounted) {
        mostrarOk(context, '${selecionados.length} convidado(s)');
        _recarregar();
      }
    } catch (e) {
      if (mounted) mostrarErro(context, e);
    }
  }

  Future<void> _convidarTurma() async {
    List<Turma> turmas;
    try {
      turmas = await TurmasService.listar();
    } catch (e) {
      if (mounted) mostrarErro(context, e);
      return;
    }
    if (turmas.isEmpty) {
      if (mounted) mostrarErro(context, 'Você não tem nenhuma turma criada ainda');
      return;
    }
    if (!mounted) return;

    final turma = await showDialog<Turma>(
      context: context,
      builder: (_) => SimpleDialog(
        title: const Text('Convidar turma inteira'),
        children: turmas
            .map((t) => SimpleDialogOption(
                  onPressed: () => Navigator.pop(context, t),
                  child: Text(t.nome),
                ))
            .toList(),
      ),
    );
    if (turma == null) return;

    try {
      final total = await EventosService.convidar(widget.eventoId, turmaIds: [turma.id]);
      if (mounted) {
        mostrarOk(context, '$total aluno(s) da turma "${turma.nome}" convidado(s)');
        _recarregar();
      }
    } catch (e) {
      if (mounted) mostrarErro(context, e);
    }
  }

  void _abrirConvite(List<String> jaConvidados) {
    showModalBottomSheet(
      context: context,
      builder: (ctx) => SafeArea(
        child: Wrap(children: [
          ListTile(
            leading: const Icon(Icons.person_add),
            title: const Text('Selecionar alunos'),
            onTap: () {
              Navigator.pop(ctx);
              _convidarAlunos(jaConvidados);
            },
          ),
          ListTile(
            leading: const Icon(Icons.groups),
            title: const Text('Convidar turma inteira'),
            onTap: () {
              Navigator.pop(ctx);
              _convidarTurma();
            },
          ),
        ]),
      ),
    );
  }

  Future<void> _editar() async {
    // O evento já está carregado no _futureEvento - reusa em vez de
    // buscar de novo só pra preencher o formulário.
    final Evento evento;
    try {
      evento = await _futureEvento;
    } catch (e) {
      if (mounted) mostrarErro(context, e);
      return;
    }
    if (!mounted) return;

    final salvou = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => CriarEventoScreen(evento: evento)),
    );
    if (salvou == true && mounted) {
      _recarregar(); // já sinaliza onMudou pra lista de trás recarregar
      mostrarOk(context, 'Evento atualizado');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: FutureBuilder<Evento>(
          future: _futureEvento,
          builder: (context, snap) => Text(snap.data?.titulo ?? 'Evento'),
        ),
        actions: widget.ehProfessor
            ? [
                PopupMenuButton<void>(
                  itemBuilder: (context) => [
                    PopupMenuItem(
                      onTap: _editar,
                      child: const Text('Editar evento'),
                    ),
                    PopupMenuItem(
                      onTap: _excluir,
                      child: Text('Excluir evento', style: TextStyle(color: CoresStatus.erro(context))),
                    ),
                  ],
                ),
              ]
            : null,
        bottom: widget.ehProfessor
            ? const TabBar(tabs: [
                Tab(text: 'Participantes'),
                Tab(text: 'Logs'),
              ])
            : null,
      ),
      body: FutureBuilder<Evento>(
        future: _futureEvento,
        builder: (context, snapEvento) {
          if (!snapEvento.hasData) {
            if (snapEvento.hasError) {
              return Center(
                child: Text(snapEvento.error is ApiException
                    ? (snapEvento.error as ApiException).mensagem
                    : 'Erro ao carregar evento'),
              );
            }
            return const Center(child: CircularProgressIndicator());
          }
          final evento = snapEvento.data!;

          final corpo = widget.ehProfessor
              ? TabBarView(children: [
                  _AbaParticipantes(
                    eventoId: widget.eventoId,
                    ehProfessor: true,
                    meuId: widget.meuId,
                    onLiberar: _liberar,
                    onRemover: _removerParticipante,
                  ),
                  _AbaLogs(eventoId: widget.eventoId),
                ])
              : _AbaParticipantes(
                  eventoId: widget.eventoId,
                  ehProfessor: false,
                  meuId: widget.meuId,
                  onLiberar: _liberar,
                  onRemover: _removerParticipante,
                );

          return Column(
            children: [
              _CabecalhoEvento(
                evento: evento,
                ehProfessor: widget.ehProfessor,
                onMudarStatus: _mudarStatus,
                onCancelar: _cancelar,
                onCancelarSerie: evento.recorrenciaId == null
                    ? null
                    : () => _cancelarSerie(evento.recorrenciaId!),
              ),
              Expanded(child: corpo),
            ],
          );
        },
      ),
      floatingActionButton: widget.ehProfessor
          ? FloatingActionButton.extended(
              onPressed: () async {
                final atuais = await EventosService.listarParticipantes(widget.eventoId);
                if (context.mounted) {
                  _abrirConvite(atuais.map((p) => p.usuarioId).toList());
                }
              },
              icon: const Icon(Icons.person_add),
              label: const Text('Convidar'),
            )
          : null,
    );
  }
}

class _CabecalhoEvento extends StatelessWidget {
  final Evento evento;
  final bool ehProfessor;
  final void Function(String status) onMudarStatus;
  final VoidCallback onCancelar;
  /// null quando o evento não faz parte de uma recorrência.
  final VoidCallback? onCancelarSerie;

  const _CabecalhoEvento({
    required this.evento,
    required this.ehProfessor,
    required this.onMudarStatus,
    required this.onCancelar,
    required this.onCancelarSerie,
  });

  Color _corStatus(BuildContext context) {
    if (evento.cancelado) return CoresStatus.erro(context);
    if (evento.emAndamento) return CoresStatus.ok(context);
    if (evento.encerrado) return CoresStatus.neutro(context);
    return Theme.of(context).colorScheme.primary;
  }

  @override
  Widget build(BuildContext context) {
    final cores = Theme.of(context).colorScheme;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 14),
      color: cores.surfaceContainerHighest.withValues(alpha: 0.4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Selo(texto: evento.status, cor: _corStatus(context)),
              if (evento.recorrenciaId != null) ...[
                const SizedBox(width: 8),
                Tooltip(
                  message: 'Faz parte de uma aula recorrente',
                  child: Icon(Icons.event_repeat, size: 17, color: cores.onSurfaceVariant),
                ),
              ],
            ],
          ),
          const SizedBox(height: 10),
          Text(
            formatarPeriodo(evento.dataInicio, evento.dataFim),
            style: Tipos.dado(
              context,
              tamanho: 13.5,
              peso: FontWeight.w500,
              cor: Theme.of(context).colorScheme.onSurface,
            ),
          ),
          if (evento.local != null && evento.local!.isNotEmpty) ...[
            const SizedBox(height: 4),
            Row(children: [
              Icon(Icons.location_on_outlined, size: 15, color: cores.onSurfaceVariant),
              const SizedBox(width: 4),
              Text(
                evento.local!,
                style: TextStyle(fontSize: 13, color: cores.onSurfaceVariant),
              ),
            ]),
          ],
          if (evento.descricao != null && evento.descricao!.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              evento.descricao!,
              style: TextStyle(fontSize: 13.5, color: cores.onSurfaceVariant, height: 1.4),
            ),
          ],
          if (ehProfessor && !evento.cancelado && !evento.encerrado) ...[
            const SizedBox(height: 12),
            Wrap(spacing: 8, children: [
              if (evento.status == 'agendado')
                OutlinedButton.icon(
                  onPressed: () => onMudarStatus('em_andamento'),
                  icon: const Icon(Icons.play_arrow),
                  label: const Text('Iniciar'),
                ),
              if (evento.status == 'em_andamento')
                OutlinedButton.icon(
                  onPressed: () => onMudarStatus('encerrado'),
                  icon: const Icon(Icons.stop),
                  label: const Text('Encerrar'),
                ),
              TextButton.icon(
                onPressed: onCancelar,
                icon: Icon(Icons.cancel_outlined, color: CoresStatus.erro(context)),
                label: Text('Cancelar', style: TextStyle(color: CoresStatus.erro(context))),
              ),
              if (onCancelarSerie != null)
                TextButton.icon(
                  onPressed: onCancelarSerie,
                  icon: Icon(Icons.event_busy, color: CoresStatus.erro(context)),
                  label: Text('Cancelar série', style: TextStyle(color: CoresStatus.erro(context))),
                ),
            ]),
          ],
        ],
      ),
    );
  }
}

class _AbaParticipantes extends StatelessWidget {
  final int eventoId;
  final bool ehProfessor;
  final String? meuId;
  final void Function(Participante) onLiberar;
  final void Function(Participante) onRemover;

  const _AbaParticipantes({
    required this.eventoId,
    required this.ehProfessor,
    required this.meuId,
    required this.onLiberar,
    required this.onRemover,
  });

  @override
  Widget build(BuildContext context) {
    if (!ehProfessor) {
      // Aluno só vê o próprio status, não a lista inteira dos colegas.
      return FutureBuilder<List<Participante>>(
        future: EventosService.listarParticipantes(eventoId),
        builder: (context, snap) {
          if (snap.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return Center(
              child: Text(snap.error is ApiException
                  ? (snap.error as ApiException).mensagem
                  : 'Erro ao carregar'),
            );
          }
          Participante? eu;
          for (final p in snap.data ?? const <Participante>[]) {
            if (p.usuarioId == meuId) {
              eu = p;
              break;
            }
          }
          if (eu == null) {
            return const Center(child: Text('Você não está convidado pra esse evento'));
          }
          final cor = switch (eu.status) {
            'liberado' => CoresStatus.ok(context),
            'negado' => CoresStatus.erro(context),
            _ => CoresStatus.alerta(context),
          };
          return Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  eu.liberado ? Icons.check_circle : Icons.hourglass_empty,
                  size: 64,
                  color: cor,
                ),
                const SizedBox(height: 12),
                Text('Status: ${eu.status}', style: Theme.of(context).textTheme.titleLarge),
                if (eu.liberadoEm != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text(
                      'Liberado em ${formatarDataHora(eu.liberadoEm!)}',
                      style: Tipos.dado(context, tamanho: 13),
                    ),
                  ),
                // Aviso enquanto ainda dá tempo de resolver: sem rosto
                // cadastrado a câmera não reconhece e a entrada trava.
                if (!eu.temRosto)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(32, 20, 32, 0),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.face_retouching_off,
                            size: 20, color: CoresStatus.alerta(context)),
                        const SizedBox(width: 8),
                        Flexible(
                          child: Text(
                            'Você ainda não cadastrou seu rosto - vai precisar '
                            'que o professor libere sua entrada na mão.',
                            style: TextStyle(color: CoresStatus.alerta(context)),
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          );
        },
      );
    }

    return ListaAsync<Participante>(
      carregar: () => EventosService.listarParticipantes(eventoId),
      mensagemVazia: 'Ninguém convidado ainda',
      iconeVazio: Icons.person_add_disabled,
      reservarEspacoFab: true,
      itemBuilder: (context, p) {
        final cor = switch (p.status) {
          'liberado' => CoresStatus.ok(context),
          'negado' => CoresStatus.erro(context),
          _ => CoresStatus.alerta(context),
        };
        return ListTile(
          // Quem não tem rosto cadastrado nunca vai ser reconhecido pela
          // câmera - marcar aqui avisa o professor antes da aula começar.
          // O selo vai no avatar (e não ao lado do nome) porque a linha já
          // tem chip + 2 botões: qualquer coisa a mais trunca o nome.
          leading: Tooltip(
            message: p.temRosto
                ? ''
                : 'Sem rosto cadastrado - só entra com liberação manual',
            child: Stack(
              clipBehavior: Clip.none,
              children: [
                CircleAvatar(child: Text(_iniciais(p.nome))),
                if (!p.temRosto)
                  Positioned(
                    right: -2,
                    bottom: -2,
                    child: Container(
                      padding: const EdgeInsets.all(1),
                      decoration: BoxDecoration(
                        color: Theme.of(context).colorScheme.surface,
                        shape: BoxShape.circle,
                      ),
                      child: Icon(
                        Icons.face_retouching_off,
                        size: 16,
                        color: CoresStatus.alerta(context),
                      ),
                    ),
                  ),
              ],
            ),
          ),
          title: Text(p.nome, overflow: TextOverflow.ellipsis),
          subtitle: Text(
            [
              if (p.matricula != null && p.matricula!.isNotEmpty) p.matricula!,
              p.origem == 'turma' ? 'via turma' : 'manual',
              // Quando a porta viu a pessoa mais de uma vez, dá pra dizer
              // por quanto tempo ela esteve por perto. Com uma leitura só,
              // a hora da entrada é tudo que se sabe — e é o que se diz.
              // "Saiu" seria invenção: ninguém é lido ao ir embora.
              if (p.temPermanencia)
                '${formatarHora(p.primeiraLeitura!)}→${formatarHora(p.ultimaLeitura!)}'
                    ' · ${_duracao(p.permanencia!)}'
              else if (p.liberadoEm != null)
                'entrou ${formatarHora(p.liberadoEm!)}',
            ].join(' · '),
            style: Tipos.dado(context),
          ),
          trailing: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Selo(texto: p.status, cor: cor),
              if (!p.liberado)
                IconButton(
                  icon: const Icon(Icons.check_circle_outline),
                  tooltip: 'Liberar manualmente',
                  onPressed: () => onLiberar(p),
                ),
              IconButton(
                icon: const Icon(Icons.close),
                tooltip: 'Remover',
                onPressed: () => onRemover(p),
              ),
            ],
          ),
        );
      },
    );
  }

  /// "1h20" / "45min". Sem segundos: a precisão que o dado tem é a da
  /// passagem pela porta, não a do relógio.
  static String _duracao(Duration d) {
    if (d.inHours == 0) return '${d.inMinutes}min';
    final min = d.inMinutes % 60;
    return min == 0 ? '${d.inHours}h' : '${d.inHours}h${min.toString().padLeft(2, '0')}';
  }
}

class _AbaLogs extends StatelessWidget {
  final int eventoId;

  const _AbaLogs({required this.eventoId});

  @override
  Widget build(BuildContext context) {
    return ListaAsync<AccessLog>(
      carregar: () => EventosService.logs(eventoId),
      mensagemVazia: 'Nenhum acesso registrado ainda',
      iconeVazio: Icons.history,
      itemBuilder: (context, log) {
        final cor = log.liberado ? CoresStatus.ok(context) : CoresStatus.erro(context);
        return ListTile(
          isThreeLine: log.motivo != null,
          leading: Icon(
            log.liberado ? Icons.check_circle : Icons.block,
            color: cor,
          ),
          title: Text(log.nome ?? 'Desconhecido'),
          subtitle: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // O motivo é o que diz o que fazer a respeito - "negado"
              // sozinho não distingue câmera ruim de pessoa errada.
              if (log.motivo != null)
                Text(
                  log.motivo!,
                  style: TextStyle(color: cor, fontWeight: FontWeight.w500),
                ),
              Text([
                formatarDataHora(log.criadoEm),
                log.porReconhecimento ? 'facial' : 'manual',
                if (log.dispositivo != null) log.dispositivo!,
              ].join(' · ')),
            ],
          ),
        );
      },
    );
  }
}

String _iniciais(String nome) {
  final partes = nome.trim().split(RegExp(r'\s+'));
  final letras = partes.take(2).map((p) => p.isEmpty ? '' : p[0]).join();
  return letras.toUpperCase();
}
