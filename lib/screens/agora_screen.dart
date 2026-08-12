import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config/tema.dart';
import '../models/evento.dart';
import '../models/participante.dart';
import '../services/auth_provider.dart';
import '../services/eventos_service.dart';
import '../utils/formatters.dart';
import 'evento_detail_screen.dart';
import 'eventos_screen.dart' show Selo;

/// A aula que está acontecendo AGORA.
///
/// É a única tela do app que muda sozinha: enquanto a aula corre, cada
/// pessoa reconhecida na porta pelo leitor facial aparece aqui em poucos
/// segundos. Para o professor é a lista de chamada se preenchendo; para
/// o aluno é a confirmação de que a catraca o reconheceu.
///
/// Não existe endpoint novo por trás disso - é a mesma /eventos e
/// /eventos/{id}/participantes que o resto do app já usa, relidas de
/// tempos em tempos.
class AgoraScreen extends StatefulWidget {
  /// Falso quando o usuário está em outra aba. As abas ficam vivas
  /// dentro do IndexedStack, então sem isto o timer seguiria batendo no
  /// servidor a cada 10s pelo app inteiro aberto, mesmo com esta tela
  /// fora de vista.
  final bool ativo;

  const AgoraScreen({super.key, this.ativo = true});

  @override
  State<AgoraScreen> createState() => _AgoraScreenState();
}

class _AgoraScreenState extends State<AgoraScreen> {
  // Curto o bastante pra parecer ao vivo, longo o bastante pra não
  // martelar o servidor. Quem libera de verdade é a Raspberry; aqui só
  // relemos o resultado.
  static const _intervalo = Duration(seconds: 10);

  Timer? _relogio;
  bool _carregando = true;
  Object? _erro;

  Evento? _agora;
  Evento? _proximo;
  List<Participante> _participantes = const [];

  @override
  void initState() {
    super.initState();
    _carregar();
    if (widget.ativo) _ligarRelogio();
  }

  @override
  void didUpdateWidget(AgoraScreen anterior) {
    super.didUpdateWidget(anterior);
    if (widget.ativo == anterior.ativo) return;
    if (widget.ativo) {
      _carregar(); // voltou pra aba: mostra o estado de agora, não o de antes
      _ligarRelogio();
    } else {
      _relogio?.cancel();
      _relogio = null;
    }
  }

  void _ligarRelogio() {
    _relogio?.cancel();
    _relogio = Timer.periodic(_intervalo, (_) => _carregar());
  }

  @override
  void dispose() {
    _relogio?.cancel();
    super.dispose();
  }

  Future<void> _carregar() async {
    // Lido antes do await: depois de um gap assíncrono o context pode
    // não valer mais.
    final ehProfessor = context.read<AuthProvider>().perfil!.isProfessor;

    try {
      final eventos = await EventosService.listar();
      final relogio = DateTime.now();

      Evento? emCurso;
      Evento? seguinte;
      for (final e in eventos) {
        if (e.cancelado) continue;
        if (!e.dataInicio.isAfter(relogio) && e.dataFim.isAfter(relogio)) {
          emCurso ??= e;
        } else if (e.dataInicio.isAfter(relogio) &&
            (seguinte == null || e.dataInicio.isBefore(seguinte.dataInicio))) {
          seguinte = e;
        }
      }

      // A lista de presença só interessa (e só é permitida) pra quem
      // conduz a aula. O aluno já recebe o próprio status no evento.
      final participantes = emCurso != null && ehProfessor
          ? await EventosService.listarParticipantes(emCurso.id)
          : const <Participante>[];

      if (!mounted) return;
      setState(() {
        _agora = emCurso;
        _proximo = seguinte;
        _participantes = participantes;
        _erro = null;
        _carregando = false;
      });
    } catch (e) {
      if (!mounted) return;
      // Uma falha de rede no meio de uma aula não pode apagar o que já
      // está na tela - só marca o erro se ainda não há nada pra mostrar.
      setState(() {
        _erro = e;
        _carregando = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_carregando) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_erro != null && _agora == null && _proximo == null) {
      return const _Vazio(
        icone: Icons.cloud_off,
        titulo: 'Não foi possível carregar',
        detalhe: 'Verifique se o servidor está no ar.',
      );
    }

    final ehProfessor = context.watch<AuthProvider>().perfil!.isProfessor;

    return RefreshIndicator(
      onRefresh: _carregar,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
        children: [
          if (_agora != null)
            ..._emAula(context, _agora!, ehProfessor)
          else
            ..._semAula(context),
        ],
      ),
    );
  }

  // ------------------------------------------------------------
  // Tem aula rolando
  // ------------------------------------------------------------

  List<Widget> _emAula(BuildContext context, Evento evento, bool ehProfessor) {
    final restante = evento.dataFim.difference(DateTime.now());
    return [
      _Cabecalho(evento: evento, restante: restante),
      const SizedBox(height: 28),
      if (ehProfessor)
        ..._presenca(context, evento)
      else ...[
        _StatusDoAluno(evento: evento),
        // O aluno resolve a dúvida dele nas duas primeiras linhas; o resto
        // da tela ficava vazio. Em vez de esticar o que já foi dito, a
        // sobra passa a responder a pergunta seguinte: "e depois?".
        if (_proximo != null) ...[
          const SizedBox(height: 36),
          Divider(color: Theme.of(context).colorScheme.outlineVariant),
          const SizedBox(height: 20),
          Text('DEPOIS DESTA', style: Tipos.etiqueta(context)),
          const SizedBox(height: 10),
          Text(_proximo!.titulo, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 4),
          Text(
            [
              formatarPeriodoCurto(_proximo!.dataInicio, _proximo!.dataFim),
              if (_proximo!.local != null && _proximo!.local!.isNotEmpty)
                _proximo!.local!,
            ].join(' · '),
            style: Tipos.dado(context),
          ),
        ],
      ],
    ];
  }

  List<Widget> _presenca(BuildContext context, Evento evento) {
    final entraram = _participantes.where((p) => p.liberado).toList()
      ..sort((a, b) => (a.liberadoEm ?? DateTime(0)).compareTo(b.liberadoEm ?? DateTime(0)));
    final faltam = _participantes.where((p) => !p.liberado).toList();
    final total = _participantes.length;

    return [
      _Contador(entraram: entraram.length, total: total),
      const SizedBox(height: 28),
      if (entraram.isNotEmpty) ...[
        _Titulo('Entraram', entraram.length),
        for (final p in entraram) _LinhaPessoa(participante: p),
        const SizedBox(height: 24),
      ],
      if (faltam.isNotEmpty) ...[
        _Titulo('Ainda não chegaram', faltam.length),
        for (final p in faltam) _LinhaPessoa(participante: p),
      ],
      if (total == 0)
        const _Vazio(
          icone: Icons.person_off_outlined,
          titulo: 'Ninguém foi convidado',
          detalhe: 'Convide a turma na tela da aula.',
        ),
      const SizedBox(height: 16),
      Center(
        child: TextButton(
          onPressed: () => Navigator.of(context)
              .push(MaterialPageRoute(
                builder: (_) => EventoDetailScreen(eventoId: evento.id),
              ))
              .then((_) => _carregar()),
          child: const Text('Abrir a aula'),
        ),
      ),
    ];
  }

  // ------------------------------------------------------------
  // Não tem aula rolando
  // ------------------------------------------------------------

  List<Widget> _semAula(BuildContext context) {
    final proximo = _proximo;
    if (proximo == null) {
      return const [
        SizedBox(height: 48),
        _Vazio(
          icone: Icons.event_available_outlined,
          titulo: 'Nenhuma aula agora',
          detalhe: 'Quando uma começar, ela aparece aqui sozinha.',
        ),
      ];
    }

    final falta = proximo.dataInicio.difference(DateTime.now());
    return [
      const SizedBox(height: 40),
      Text('PRÓXIMA AULA', style: Tipos.etiqueta(context)),
      const SizedBox(height: 12),
      Text(proximo.titulo, style: Theme.of(context).textTheme.headlineSmall),
      const SizedBox(height: 8),
      Text(
        'começa em ${formatarDuracaoCurta(falta)}'
        '${proximo.local != null ? ' · ${proximo.local}' : ''}',
        style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
      ),
      const SizedBox(height: 6),
      Text(
        formatarPeriodoCurto(proximo.dataInicio, proximo.dataFim),
        style: Tipos.dado(context),
      ),
    ];
  }
}

// ------------------------------------------------------------
// Pedaços
// ------------------------------------------------------------

class _Cabecalho extends StatelessWidget {
  final Evento evento;
  final Duration restante;

  const _Cabecalho({required this.evento, required this.restante});

  @override
  Widget build(BuildContext context) {
    final cores = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            // Ponto pulsante seria enfeite; o texto "acontecendo agora"
            // já diz o que precisa, e sobra atenção pro número.
            Container(
              width: 7,
              height: 7,
              decoration: BoxDecoration(
                color: CoresStatus.ok(context),
                shape: BoxShape.circle,
              ),
            ),
            const SizedBox(width: 8),
            Text(
              'ACONTECENDO AGORA',
              style: Tipos.etiqueta(context, cor: CoresStatus.ok(context)),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Text(evento.titulo, style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 6),
        Text(
          '${evento.local ?? 'Sem local'} · termina em ${formatarDuracaoCurta(restante)}',
          style: TextStyle(color: cores.onSurfaceVariant),
        ),
      ],
    );
  }
}

/// O número que o professor quer ver de longe.
class _Contador extends StatelessWidget {
  final int entraram;
  final int total;

  const _Contador({required this.entraram, required this.total});

  @override
  Widget build(BuildContext context) {
    final cores = Theme.of(context).colorScheme;
    final cor = entraram > 0 ? CoresStatus.ok(context) : cores.onSurfaceVariant;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.baseline,
          textBaseline: TextBaseline.alphabetic,
          children: [
            Text('$entraram', style: Tipos.numeral(context, cor: cor)),
            Text(
              ' / $total',
              style: Tipos.dado(context, tamanho: 19, cor: cores.onSurfaceVariant),
            ),
            const Spacer(),
            Text(
              'entraram',
              style: TextStyle(fontSize: 13.5, color: cores.onSurfaceVariant),
            ),
          ],
        ),
        const SizedBox(height: 14),
        ClipRRect(
          borderRadius: BorderRadius.circular(3),
          child: LinearProgressIndicator(
            value: total == 0 ? 0 : entraram / total,
            minHeight: 5,
            backgroundColor: cores.surfaceContainerHighest,
            valueColor: AlwaysStoppedAnimation(cor),
          ),
        ),
      ],
    );
  }
}

class _Titulo extends StatelessWidget {
  final String texto;
  final int quantidade;

  const _Titulo(this.texto, this.quantidade);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Text(
        '${texto.toUpperCase()} · $quantidade',
        style: Tipos.etiqueta(context),
      ),
    );
  }
}

class _LinhaPessoa extends StatelessWidget {
  final Participante participante;

  const _LinhaPessoa({required this.participante});

  @override
  Widget build(BuildContext context) {
    final cores = Theme.of(context).colorScheme;
    final entrou = participante.liberado;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 9),
      child: Row(
        children: [
          // Barra fina no lugar de avatar: numa lista de 30 alunos, 30
          // bolinhas viram parede e não informam nada.
          Container(
            width: 3,
            height: 26,
            decoration: BoxDecoration(
              color: entrou ? CoresStatus.ok(context) : cores.outlineVariant,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  participante.nome,
                  style: const TextStyle(fontSize: 15),
                  overflow: TextOverflow.ellipsis,
                ),
                if (participante.matricula != null)
                  Text(participante.matricula!, style: Tipos.dado(context)),
              ],
            ),
          ),
          if (entrou && participante.liberadoEm != null)
            // O horário da entrada é o registro em si: mono, e na cor de
            // liberado, porque é a prova de que a catraca abriu.
            Text(
              formatarHora(participante.liberadoEm!),
              style: Tipos.dado(
                context,
                tamanho: 13.5,
                peso: FontWeight.w500,
                cor: CoresStatus.ok(context),
              ),
            )
          // Sem rosto cadastrado essa pessoa nunca vai ser liberada pela
          // câmera - avisar aqui evita o professor esperar por alguém que
          // o leitor não tem como reconhecer.
          else if (!participante.temRosto)
            Selo(texto: 'sem rosto', cor: CoresStatus.alerta(context)),
        ],
      ),
    );
  }
}

class _StatusDoAluno extends StatelessWidget {
  final Evento evento;

  const _StatusDoAluno({required this.evento});

  @override
  Widget build(BuildContext context) {
    final liberado = evento.meuStatus == 'liberado';
    final cor = liberado ? CoresStatus.ok(context) : CoresStatus.alerta(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(liberado ? Icons.check_circle : Icons.schedule, color: cor, size: 26),
            const SizedBox(width: 10),
            Text(
              liberado ? 'Entrada liberada' : 'Aguardando você',
              style: TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.w600,
                color: cor,
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        Text(
          liberado
              ? 'A câmera da porta já reconheceu você nesta aula.'
              : 'Olhe para a câmera na porta${evento.local != null ? ' da ${evento.local}' : ''} para entrar.',
          style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
        ),
      ],
    );
  }
}

class _Vazio extends StatelessWidget {
  final IconData icone;
  final String titulo;
  final String detalhe;

  const _Vazio({required this.icone, required this.titulo, required this.detalhe});

  @override
  Widget build(BuildContext context) {
    final cor = Theme.of(context).colorScheme.outline;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 40),
      child: Column(
        children: [
          Icon(icone, size: 52, color: cor),
          const SizedBox(height: 14),
          Text(titulo, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 6),
          Text(
            detalhe,
            textAlign: TextAlign.center,
            style: TextStyle(color: cor),
          ),
        ],
      ),
    );
  }
}
