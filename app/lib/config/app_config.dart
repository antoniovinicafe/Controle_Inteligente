/// Preencha com os dados do SEU projeto:
///
/// SUPABASE_URL e SUPABASE_ANON_KEY:
///   Supabase Dashboard > Project Settings > API
///   - "Project URL" -> supabaseUrl
///   - "anon public" key -> supabaseAnonKey
///
///   ATENÇÃO: a anon key só é segura no app se as tabelas tiverem
///   Row Level Security (RLS) ligado no Postgres. Sem RLS, quem extrair
///   essa chave do APK lê e escreve o banco inteiro direto pela API do
///   Supabase, passando por cima do Flask e de todo o `@login_required`.
///   Confira em Supabase Dashboard > Authentication > Policies.
///
/// apiBaseUrl:
///   Endereço onde o Flask está rodando. O padrão abaixo (10.0.2.2) só
///   funciona no emulador Android, que enxerga a máquina host por esse
///   alias. Num celular físico, passe o IP da máquina na rede:
///
///     flutter run --dart-define=API_BASE_URL=http://192.168.0.10:5000/api
///
///   (troque pelo IP que o Flask mostra ao subir, em "Running on http://...")
///   Isso evita ter que editar este arquivo e lembrar de desfazer depois.
class AppConfig {
  static const supabaseUrl = 'https://udslgrllcgsmlwktuweb.supabase.co';
  static const supabaseAnonKey = 'sb_publishable_5WE15j_FkEOaTGNOff-SNw_VfElDcsG';

  static const apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:5000/api',
  );
}
