import type { ScreenDefinition } from '../lib/screens'

type PlaceholderPageProps = {
  screen: ScreenDefinition
}

export function PlaceholderPage({ screen }: PlaceholderPageProps) {
  return (
    <section className="grid min-h-[calc(100svh-2rem)] place-items-center">
      <div className="max-w-xl rounded-panel bg-surfaceContainer p-10">
        <p className="text-xs uppercase tracking-[0.16em] text-primary">
          Phase {screen.id}
        </p>
        <h2 className="mt-3 font-headline text-3xl font-extrabold text-onSurface">
          {screen.title}
        </h2>
        <p className="mt-4 text-sm leading-7 text-onSurfaceMuted">
          This screen is queued and will be implemented in the next phase. Source
          folder: <span className="text-onSurface">{screen.folder}</span>
        </p>
      </div>
    </section>
  )
}
