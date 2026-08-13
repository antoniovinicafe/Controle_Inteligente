import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config/tema.dart';
import '../models/evento.dart';
import '../models/frequencia.dart';
import '../services/auth_provider.dart';
import '../services/eventos_service.dart';
import '../services/usuarios_service.dart';
import '../utils/formatters.dart';
import '../widgets/lista_async.dart';
import 'criar_evento_screen.dart';
import 'evento_detail_screen.dart';

class EventosScreen extends StatefulWidget {
  const EventosScreen({super.key});

  @override
  State<EventosScreen> createState() => _EventosScreenState();
}

class _EventosScreenState extends State<EventosScreen> {
  // Muda a cada recarga forçada de fora (criar/editar/cancelar evento) -
  // usado como key do ListaAsync pra garantir remontagem completa em vez
  // de depender do FutureBuilder perceber a troca de Future sozinho.
  int _versao = 0;

  /// Só o aluno vê frequência; null enquanto carrega ou se der erro.
  Frequencia? _frequencia;
  List<FrequenciaDaTurma> _porTurma = [];

  @override
  void initState() {
    super.initState();
    _carregarFrequencia();
  }

  Future<void> _carregarFrequencia() async {
    if (!mounted) return;
    if (context.read<AuthProvider>().perfil?.isProfessor ?? true) return;
    try {
      final f = await UsuariosService.minhaFrequencia();
      if (mounted) {
        setState(() {
          _frequencia = f.geral;
          _porTurma = f.turmas;
        });
      }
    } catch (_) {
      // Frequência é informativa: se falhar, a lista de eventos continua.
    }
  }

  void _recarregar() => setState(() => _versao++);

  /// Faixa do topo da lista do aluno: primeiro o que exige ação (aula
  /// cancelada), depois o resumo de presença.
  Widget? _topoDoAluno(BuildContext context, List<Evento> eventos) {
    final cancelamentos = _avisoCancelamentos(context, eventos);
    final avisos = <Widget>[
      if (cancelamentos != null) cancelamentos,
      if (_frequencia != null && !_frequencia!.semAulas)
        _CardFrequencia(frequencia: _frequencia!, porTurma: _porTurma),
    ];
    if (avisos.isEmpty) return null;
    return Column(children: avisos);
  }

  Future<void> _criarEvento() async {
    final criado = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => const CriarEventoScreen()),
    );
    if (criado == true) _recarregar();
  }

  @override
  Widget build(BuildContext context) {
    final ehProfessor = context.watch<AuthProvider>().perfil?.isProfessor ?? false;

    // Sem AppBar de propósito: esta tela é uma aba dentro da HomeScreen, que
    // já tem a sua (nome + papel de quem está logado). O título "Eventos"
    // repetia o que a barra de navegação de baixo já diz - e diz melhor,
    // porque lá o item fica destacado. O Scaffold continua aqui pelo FAB.
    return Scaffold(
      body: ListaAsync<Evento>(
        key: ValueKey(_versao),
        carregar: EventosService.listar,
        mensagemVazia: ehProfessor
            ? 'Você ainda não criou nenhum evento'
            : 'Você ainda não foi convidado pra nenhum evento',
        iconeVazio: Icons.event_busy,
        reservarEspacoFab: ehProfessor,
        // Só pro aluno: quem cancelou já sabe que cancelou.
        cabecalho: ehProfessor ? null : _topoDoAluno,
        itemBuilder: (context, e) => _LinhaEvento(
          evento: e,
          ehProfessor: ehProfessor,
          onTap: () async {
            final mudou = await Navigator.of(context).push<bool>(
              MaterialPageRoute(
                builder: (_) => EventoDetailScreen(eventoId: e.id),
              ),
            );
            if (mudou == true) _recarregar();
          },
        ),
      ),
      floatingActionButton: ehProfessor
          ? FloatingActionButton.extended(
              onPressed: _criarEvento,
              icon: const Icon(Icons.add),
              label: const Text('Novo evento'),
            )
          : null,
    );
  }
}

/// Aviso no topo da lista do aluno quando alguma aula da semana caiu.
///
/// O aluno já recebia esses eventos na lista, mas misturados com os
/// outros - dava pra ir pra uma aula cancelada sem perceber. Aqui não há
/// tabela de notificação nem controle de lido: a janela de 7 dias faz o
/// aviso sumir sozinho quando deixa de ser acionável.
Widget? _avisoCancelamentos(BuildContext context, List<Evento> eventos) {
  final agora = DateTime.now();
  final limite = agora.add(const Duration(days: 7));
  final caidas = eventos
      .where((e) => e.cancelado &&
          e.dataInicio.isAfter(agora) &&
          e.dataInicio.isBefore(limite))
      .toList()
    ..sort((a, b) => a.dataInicio.compareTo(b.dataInicio));

  if (caidas.isEmpty) return null;

  final cor = CoresStatus.erro(context);
  return Container(
    margin: const EdgeInsets.fromLTRB(16, 6, 16, 12),
    padding: const EdgeInsets.fromLTRB(14, 12, 14, 13),
    decoration: BoxDecoration(
      color: CoresStatus.fundo(context, cor),
      borderRadius: BorderRadius.circular(14),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(Icons.event_busy_outlined, color: cor, size: 17),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                caidas.length == 1
                    ? 'Uma aula sua foi cancelada'
                    : '${caidas.length} aulas suas foram canceladas',
                style: TextStyle(
                  color: cor,
                  fontWeight: FontWeight.w600,
                  fontSize: 13.5,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 7),
        for (final e in caidas)
          Padding(
            padding: const EdgeInsets.only(top: 3, left: 25),
            child: Text(
              '${e.titulo}  ·  ${formatarPeriodo(e.dataInicio, e.dataFim)}',
              style: TextStyle(color: cor, fontSize: 12.5, height: 1.3),
            ),
          ),
      ],
    ),
  );
}

/// Um evento na lista.
///
/// Em vez de card com avatar colorido (que vira um paredão de bolhas numa
/// lista longa), é uma linha: barra fina de status na esquerda, título com
/// peso, metadados em texto menor e apagado. A separação entre itens vem
/// do espaço em branco, não de moldura.
class _LinhaEvento extends StatelessWidget {
  final Evento evento;
  final bool ehProfessor;
  final VoidCallback onTap;

  const _LinhaEvento({
    required this.evento,
    required this.ehProfessor,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final cores = Theme.of(context).colorScheme;

    // A cor segue o relógio, não o campo `status` do banco - ele só vira
    // 'em_andamento' se alguém mudar à mão, então uma aula acontecendo
    // agora aparecia com a cor de "ainda vai acontecer".
    final agora = DateTime.now();
    final rolandoAgora = !evento.cancelado &&
        !evento.dataInicio.isAfter(agora) &&
        evento.dataFim.isAfter(agora);

    final cor = evento.cancelado
        ? CoresStatus.erro(context)
        : rolandoAgora
            ? CoresStatus.ok(context)
            : evento.encerrado || evento.dataFim.isBefore(agora)
                ? CoresStatus.neutro(context)
                : cores.primary;

    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 3,
              height: 38,
              margin: const EdgeInsets.only(top: 2, right: 14),
              decoration: BoxDecoration(
                color: cor,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    evento.titulo,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: 15.5,
                      fontWeight: FontWeight.w500,
                      // Encerrado/cancelado não precisa gritar tanto quanto
                      // o que ainda vai acontecer.
                      color: evento.cancelado || evento.encerrado
                          ? cores.onSurfaceVariant
                          : cores.onSurface,
                      decoration:
                          evento.cancelado ? TextDecoration.lineThrough : null,
                      decorationColor: cores.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    [
                      formatarPeriodoCurto(evento.dataInicio, evento.dataFim),
                      if (evento.local != null && evento.local!.isNotEmpty)
                        evento.local!,
                    ].join(' · '),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    // Data, hora e sala são registro, não redação: mono
                    // alinha uma linha com a de baixo e deixa a lista
                    // varrível de cima a baixo.
                    style: Tipos.dado(
                      context,
                      cor: cores.onSurfaceVariant,
                    ).copyWith(height: 1.35),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 10),
            Padding(
              padding: const EdgeInsets.only(top: 1),
              child: _Badge(evento: evento, ehProfessor: ehProfessor),
            ),
          ],
        ),
      ),
    );
  }
}

/// Resumo de presença do aluno. Verde/laranja/vermelho seguem a régua
/// acadêmica usual: 75% é o piso pra aprovação por frequência.
/// Frequência do aluno: uma linha por disciplina.
///
/// A versão anterior mostrava só o total somado, e isso é academicamente
/// sem sentido — reprovação por falta é POR disciplina. Alguém com 80% no
/// agregado pode estar com 50% numa matéria, e o card dizia que estava tudo
/// bem. Agora o número grande é o da pior disciplina, que é a que exige
/// atenção; o resto vem listado embaixo.
class _CardFrequencia extends StatelessWidget {
  final Frequencia frequencia;
  final List<FrequenciaDaTurma> porTurma;

  const _CardFrequencia({required this.frequencia, required this.porTurma});

  /// A disciplina em pior situação — e é ela que decide o semestre.
  FrequenciaDaTurma? get _pior {
    final comAula = porTurma.where((t) => !t.frequencia.semAulas).toList();
    if (comAula.isEmpty) return null;
    comAula.sort((a, b) =>
        (a.frequencia.percentual ?? 100).compareTo(b.frequencia.percentual ?? 100));
    return comAula.first;
  }

  @override
  Widget build(BuildContext context) {
    final cores = Theme.of(context).colorScheme;
    final pior = _pior;
    final destaque = pior?.frequencia ?? frequencia;
    final pct = destaque.percentual ?? 0;
    final cor = corDaFrequencia(context, pct);

    return Card(
      margin: const EdgeInsets.fromLTRB(16, 6, 16, 12),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    pior == null ? 'Sua frequência' : 'Sua frequência em ${pior.turma}',
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                ),
                Text('$pct%', style: Tipos.numeral(context, cor: cor, tamanho: 22)),
              ],
            ),
            const SizedBox(height: 8),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: pct / 100,
                minHeight: 7,
                color: cor,
                backgroundColor: cores.surfaceContainerHighest,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              _resumo(destaque),
              style: TextStyle(color: cores.onSurfaceVariant),
            ),
            // O aviso que faz o número virar decisão. Só aparece quando
            // ainda dá pra agir - avisar cedo demais ensina a ignorar.
            if (destaque.reprovadoPorFalta || destaque.noLimite) ...[
              const SizedBox(height: 10),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.error_outline, size: 16, color: cor),
                  const SizedBox(width: 7),
                  Expanded(
                    child: Text(
                      destaque.reprovadoPorFalta
                          ? 'Você passou do limite de faltas desta disciplina.'
                          : destaque.faltasRestantes == 0
                              ? 'Mais uma falta e você reprova por frequência.'
                              : 'Você ainda pode faltar 1 vez nesta disciplina.',
                      style: TextStyle(fontSize: 12.5, color: cor),
                    ),
                  ),
                ],
              ),
            ],
            if (porTurma.length > 1) ...[
              const Divider(height: 22),
              ...porTurma.map((t) => _linhaTurma(context, t)),
            ],
          ],
        ),
      ),
    );
  }

  String _resumo(Frequencia f) {
    final aulas = '${f.presencas} de ${f.total} ${f.total == 1 ? 'aula' : 'aulas'}';
    if (f.reprovadoPorFalta) return '$aulas · ${f.faltas} faltas';
    return '$aulas · pode faltar mais ${f.faltasRestantes}';
  }

  Widget _linhaTurma(BuildContext context, FrequenciaDaTurma t) {
    final f = t.frequencia;
    final pct = f.percentual;
    final cor = corDaFrequencia(context, pct ?? 100);

    return Padding(
      padding: const EdgeInsets.only(top: 7),
      child: Row(
        children: [
          Expanded(child: Text(t.turma, style: const TextStyle(fontSize: 13.5))),
          Text(
            // Sem aula encerrada não há percentual: "0%" pareceria péssima
            // frequência em vez de "ainda não começou".
            pct == null ? '—' : '$pct%',
            style: Tipos.dado(context).copyWith(color: pct == null ? null : cor),
          ),
        ],
      ),
    );
  }
}

/// Régua acadêmica de frequência: 75% é o piso pra aprovação por presença,
/// e abaixo de 60% já é caso perdido. Vive aqui porque a tela do professor
/// (selo por aluno) precisa exatamente da mesma escala.
Color corDaFrequencia(BuildContext context, int percentual) {
  if (percentual >= 75) return CoresStatus.ok(context);
  if (percentual >= 60) return CoresStatus.alerta(context);
  return CoresStatus.erro(context);
}

class _Badge extends StatelessWidget {
  final Evento evento;
  final bool ehProfessor;

  const _Badge({required this.evento, required this.ehProfessor});

  @override
  Widget build(BuildContext context) {
    final cores = Theme.of(context).colorScheme;

    if (ehProfessor) {
      final total = evento.totalParticipantes ?? 0;
      final liberados = evento.totalLiberados ?? 0;
      // Presença é razão, não rótulo: o número liberado em destaque e o
      // total apagado lê mais rápido que um chip.
      return RichText(
        text: TextSpan(
          style: Tipos.dado(context, tamanho: 13.5, cor: cores.onSurfaceVariant),
          children: [
            TextSpan(
              text: '$liberados',
              style: TextStyle(
                fontWeight: FontWeight.w600,
                color: liberados > 0 ? CoresStatus.ok(context) : cores.onSurfaceVariant,
              ),
            ),
            TextSpan(text: '/$total'),
          ],
        ),
      );
    }

    final status = evento.meuStatus ?? 'convidado';
    final cor = switch (status) {
      'liberado' => CoresStatus.ok(context),
      'negado' => CoresStatus.erro(context),
      _ => CoresStatus.neutro(context),
    };
    return Selo(texto: status, cor: cor);
  }
}

/// Pastilha de status. Existe pra que todo rótulo do app tenha o mesmo
/// formato - antes cada tela montava o seu com padding e raio diferentes.
class Selo extends StatelessWidget {
  final String texto;
  final Color cor;

  const Selo({super.key, required this.texto, required this.cor});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
      decoration: BoxDecoration(
        color: CoresStatus.fundo(context, cor),
        borderRadius: BorderRadius.circular(7),
      ),
      // O texto do selo é um estado que o sistema atribuiu ("liberado",
      // "convidado"), não uma palavra que alguém escolheu - por isso mono,
      // igual aos rótulos da trilha no leitor da porta.
      child: Text(
        texto,
        style: Tipos.dado(context, tamanho: 11, peso: FontWeight.w500, cor: cor),
      ),
    );
  }
}
