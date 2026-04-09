import ArchivePage from "@/widgets/archive/ui/archive-page";

type PageProps = {
  params: Promise<{
    corpusItemId: string;
  }>;
};

export default async function Page({ params }: PageProps) {
  const { corpusItemId } = await params;
  return <ArchivePage initialItemId={corpusItemId} />;
}
