/// Presença em aulas já encerradas. Aula cancelada ou que ainda não
/// terminou não entra na conta - quem decide isso é o backend.
class Frequencia {
  final int total;
  final int presencas;
  final int faltas;

  /// Null quando ainda não houve nenhuma aula: mostrar "0%" nesse caso
  /// pareceria péssima frequência em vez de "ainda não teve aula".
  final int? percentual;

  /// Quantas faltas ainda cabem no semestre, contando as aulas que ainda
  /// vão acontecer. É o número que dá pra agir em cima - o percentual é um
  /// retrato do passado, este aqui é um aviso a tempo.
  final int faltasRestantes;

  /// Já passou do que o semestre comporta.
  final bool reprovadoPorFalta;

  const Frequencia({
    required this.total,
    required this.presencas,
    required this.faltas,
    required this.percentual,
    this.faltasRestantes = 0,
    this.reprovadoPorFalta = false,
  });

  bool get semAulas => total == 0;

  /// Uma falta separa a pessoa do limite. O aviso vale a pena aqui e não
  /// antes: avisar cedo demais ensina a ignorar o aviso.
  bool get noLimite => !reprovadoPorFalta && faltasRestantes <= 1;

  factory Frequencia.fromJson(Map<String, dynamic> json) => Frequencia(
        total: (json['total'] as num).toInt(),
        presencas: (json['presencas'] as num).toInt(),
        faltas: (json['faltas'] as num).toInt(),
        percentual: (json['percentual'] as num?)?.toInt(),
        // Ausentes num servidor mais antigo: o app continua funcionando,
        // só sem o aviso.
        faltasRestantes: (json['faltas_restantes'] as num?)?.toInt() ?? 0,
        reprovadoPorFalta: json['reprovado_por_falta'] == true,
      );
}

/// A frequência numa disciplina. É esta que decide aprovação — o número
/// somado de todas as turmas não decide nada, porque a regra dos 75% é por
/// disciplina.
class FrequenciaDaTurma {
  final int? turmaId;
  final String turma;
  final Frequencia frequencia;

  const FrequenciaDaTurma({
    required this.turmaId,
    required this.turma,
    required this.frequencia,
  });

  factory FrequenciaDaTurma.fromJson(Map<String, dynamic> json) => FrequenciaDaTurma(
        turmaId: (json['turma_id'] as num?)?.toInt(),
        turma: json['turma'] as String,
        frequencia: Frequencia.fromJson(json),
      );
}

/// A frequência de um aluno, do ponto de vista do professor.
class AlunoFrequencia {
  final String id;
  final String nome;
  final String? matricula;

  /// Deduzido do e-mail institucional pelo servidor (gec -> Computação,
  /// get -> Telecomunicações). Null quando o e-mail não é do Inatel.
  /// Ninguém digita isso, então não tem como divergir do cadastro.
  final String? curso;

  final Frequencia frequencia;

  const AlunoFrequencia({
    required this.id,
    required this.nome,
    required this.matricula,
    required this.curso,
    required this.frequencia,
  });

  factory AlunoFrequencia.fromJson(Map<String, dynamic> json) => AlunoFrequencia(
        id: json['id'] as String,
        nome: json['nome'] as String,
        matricula: json['matricula'] as String?,
        curso: json['curso'] as String?,
        frequencia: Frequencia.fromJson(json),
      );
}
