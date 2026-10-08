from contracts.interfaces import Renderer
from contracts.schemas import (
    Chunk,
    CitationRender,
    Claim,
    Contradiction,
    GroundedOutput,
    MissingItem,
    WorkflowName,
)


class MarkdownRenderer(Renderer):
    def render(self, workflow: WorkflowName, claims: list[Claim], chunks: dict[str, Chunk], *, missing: list[MissingItem], contradictions: list[Contradiction]) -> GroundedOutput:
        
        md_lines = [f"# LexTrace {workflow.capitalize()} Report\n"]
        
        citations = []
        cit_counter = 1
        
        if claims:
            md_lines.append("## Supported Claims")
            for claim in claims:
                claim_cits = []
                for ev in claim.evidence:
                    cit = CitationRender(
                        marker=f"[{cit_counter}]",
                        text=f"Doc {ev.chunk_id}",
                        chunk_id=ev.chunk_id,
                        quote=ev.quote
                    )
                    citations.append(cit)
                    claim_cits.append(cit.marker)
                    cit_counter += 1
                
                md_lines.append(f"- {claim.text} {' '.join(claim_cits)}")
        
        if missing:
            md_lines.append("\n## Missing Information")
            for m in missing:
                md_lines.append(f"- **{m.slot}**: {m.why_needed} (Searched: {', '.join(m.queries_tried)})")
                
        if contradictions:
            md_lines.append("\n## Contradictions Detected")
            for c in contradictions:
                md_lines.append(f"- {c.explanation}")

        return GroundedOutput(
            workflow=workflow,
            rendered_markdown="\n".join(md_lines),
            claims=claims,
            citations=citations,
            missing_info=missing,
            contradictions=contradictions,
            confidence=1.0,
            abstained=False,
            trace=[]
        )
