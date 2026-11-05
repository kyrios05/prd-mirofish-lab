import { Component, type ErrorInfo, type ReactNode, useEffect, useState, useRef } from 'react';
import type { NodeObject } from 'force-graph';
import { Box, Paper, Text, Group, Button, Badge, Progress, ScrollArea, Slider, Stack, Tooltip } from '@mantine/core';

interface Props {
  sessionId: string;
  performAction: (actionId: string, payload?: Record<string, unknown>) => Promise<void>;
}

interface EventLog {
  type: string;
  timestamp: string;
  message?: string;
  agent_name?: string;
  agent_type?: string;
  content?: string;
  reply_to?: string;
  round?: number;
  stance?: 'challenge' | 'support' | 'compromise';
  claim_reference?: string;
}

interface GraphNode extends NodeObject {
  birthTime?: number;
  role?: string;
  summary?: string;
  persona?: string;
  goal?: string;
  id: string;
  group: number;
  label?: string;
}

interface GraphLink {
  birthTime?: number;
  source: string | GraphNode;
  target: string | GraphNode;
  weight?: number;
  label?: string;
}

interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

interface NodeDetails {
  name: string;
  role: string;
  persona: string;
  goal: string;
}

function getEndpointId(endpoint: unknown): string | null {
  if (typeof endpoint === 'string' || typeof endpoint === 'number') {
    return String(endpoint);
  }

  if (endpoint && typeof endpoint === 'object' && 'id' in endpoint) {
    const id = (endpoint as { id?: unknown }).id;
    if (typeof id === 'string' || typeof id === 'number') {
      return String(id);
    }
  }

  return null;
}

class GraphErrorBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean }
> {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Simulation graph render failed', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <Box style={{ height: '100%', display: 'grid', placeItems: 'center' }}>
          <Text c="red.4" size="sm">시뮬레이션 그래프를 표시하지 못했습니다. 새로고침 후 다시 시도해주세요.</Text>
        </Box>
      );
    }

    return this.props.children;
  }
}

function SimulationNodeGraph({
  nodes,
  links,
  selectedNodeId,
  hoveredNodeId,
  onNodeClick,
  onNodeHover,
  nodeDetails,
  nodeSize,
}: {
  nodes: GraphNode[];
  links: GraphLink[];
  selectedNodeId: string | null;
  hoveredNodeId: string | null;
  onNodeClick: (node: GraphNode) => void;
  onNodeHover: (node: GraphNode | null) => void;
  nodeDetails: (node: GraphNode) => NodeDetails;
  nodeSize: number;
}) {
  const groupColors = ['#3b82f6', '#10b981', '#eab308', '#a855f7', '#ef4444', '#f97316', '#64748b'];
  const width = 1100;
  const height = 680;
  const centerX = width / 2;
  const centerY = height / 2;
  const groups = new Map<number, GraphNode[]>();
  nodes.forEach((node) => {
    const groupNodes = groups.get(node.group) || [];
    groupNodes.push(node);
    groups.set(node.group, groupNodes);
  });
  const groupIds = [...groups.keys()].sort((left, right) => left - right);
  const positions = new Map<string, { x: number; y: number }>();
  groupIds.forEach((group, groupIndex) => {
    const groupNodes = groups.get(group) || [];
    const baseAngle = (groupIndex / Math.max(groupIds.length, 1)) * Math.PI * 2 - Math.PI / 2;
    groupNodes.forEach((node, nodeIndex) => {
      const offset = (nodeIndex - (groupNodes.length - 1) / 2) * 0.18;
      const radius = 190 + (nodeIndex % 3) * 52;
      positions.set(node.id, {
        x: centerX + Math.cos(baseAngle + offset) * radius,
        y: centerY + Math.sin(baseAngle + offset) * radius,
      });
    });
  });
  const topicNode = nodes.find((node) => node.id === 'topic');
  if (topicNode) {
    positions.set(topicNode.id, { x: centerX, y: centerY });
  }

  return (
    <Box
      style={{
        position: 'absolute',
        inset: 0,
        overflow: 'auto',
        padding: '110px 24px 150px',
      }}
    >
      {nodes.length === 0 ? (
        <Text c="dimmed" ta="center" mt="xl">시뮬레이션 노드를 준비하고 있습니다.</Text>
      ) : (
        <Box style={{ height, minWidth: width, position: 'relative' }}>
          <style>{`
            @keyframes simulation-node-enter {
              from { opacity: 0; transform: translate(-50%, -50%) scale(0.35); }
              to { opacity: 1; transform: translate(-50%, -50%) scale(1); }
            }
            @keyframes simulation-edge-draw {
              from { stroke-dashoffset: 1; opacity: 0; }
              to { stroke-dashoffset: 0; opacity: 1; }
            }
          `}</style>
          <svg
            aria-label="Simulation network edges"
            height={height}
            style={{ inset: 0, pointerEvents: 'none', position: 'absolute' }}
            viewBox={`0 0 ${width} ${height}`}
            width={width}
          >
            <defs>
              <marker id="simulation-edge-arrow" markerHeight="6" markerWidth="6" orient="auto" refX="7" refY="3">
                <path d="M0,0 L0,6 L6,3 z" fill="rgba(125, 211, 252, 0.72)" />
              </marker>
              <marker id="simulation-risk-edge-arrow" markerHeight="6" markerWidth="6" orient="auto" refX="7" refY="3">
                <path d="M0,0 L0,6 L6,3 z" fill="rgba(248, 113, 113, 0.8)" />
              </marker>
            </defs>
            {links.map((link, index) => {
              const sourceId = getEndpointId(link.source);
              const targetId = getEndpointId(link.target);
              const source = sourceId ? positions.get(sourceId) : undefined;
              const target = targetId ? positions.get(targetId) : undefined;
              if (!source || !target) return null;
              const isRiskEdge = nodes.some((node) => node.id === sourceId && node.group === 4)
                || nodes.some((node) => node.id === targetId && node.group === 4);
              const weight = Math.max(1, link.weight || 1);
              return (
                <line
                  key={`${sourceId}-${targetId}-${index}`}
                  markerEnd={`url(#${isRiskEdge ? 'simulation-risk-edge-arrow' : 'simulation-edge-arrow'})`}
                  pathLength={1}
                  stroke={isRiskEdge ? 'rgba(248, 113, 113, 0.62)' : 'rgba(125, 211, 252, 0.42)'}
                  strokeWidth={Math.min(1.6 + (weight - 1) * 1.35, 8)}
                  style={{ animation: 'simulation-edge-draw 520ms ease-out forwards', strokeDasharray: 1, strokeDashoffset: 1 }}
                  x1={source.x}
                  x2={target.x}
                  y1={source.y}
                  y2={target.y}
                />
              );
            })}
          </svg>
          {nodes.map((node) => {
            const color = groupColors[node.group % groupColors.length] || '#94a3b8';
            const isSelected = selectedNodeId === node.id;
            const isHovered = hoveredNodeId === node.id;
            const position = positions.get(node.id);
            const details = nodeDetails(node);
            const diameter = node.id === 'topic'
              ? Math.max(112, Math.min(156, nodeSize * 10))
              : Math.max(78, Math.min(126, nodeSize * 7));
            if (!position) return null;

            return (
              <Tooltip
                key={node.id}
                label={
                  <Stack gap={5} style={{ maxWidth: 280 }}>
                    <Text fw={800} size="sm" c="cyan.3">{details.name}</Text>
                    <Text size="xs" c="gray.4">{details.role}</Text>
                    <Text size="xs">{details.persona}</Text>
                    <Text size="xs" c="teal.3">검증 목표: {details.goal}</Text>
                  </Stack>
                }
                multiline
                position="top"
                withArrow
              >
                <button
                  type="button"
                  onClick={() => onNodeClick(node)}
                  onMouseEnter={() => onNodeHover(node)}
                  onMouseLeave={() => onNodeHover(null)}
                  aria-label={`${details.name}: ${details.role}`}
                  style={{
                    alignItems: 'center',
                    animation: 'simulation-node-enter 420ms cubic-bezier(0.16, 1, 0.3, 1) both',
                    appearance: 'none',
                    background: isSelected || isHovered ? 'rgba(14, 116, 144, 0.48)' : 'rgba(15, 23, 42, 0.92)',
                    border: `2px solid ${isSelected || isHovered ? '#38bdf8' : color}`,
                    borderRadius: '50%',
                    boxShadow: isSelected || isHovered ? `0 0 24px ${color}88` : 'none',
                    color: '#f8fafc',
                    cursor: 'pointer',
                    display: 'flex',
                    fontSize: 11,
                    fontWeight: 700,
                    height: diameter,
                    justifyContent: 'center',
                    left: position.x,
                    lineHeight: 1.25,
                    overflow: 'hidden',
                    padding: 10,
                    position: 'absolute',
                    textAlign: 'center',
                    top: position.y,
                    transform: 'translate(-50%, -50%)',
                    width: diameter,
                    zIndex: isSelected || isHovered ? 2 : 1,
                  }}
                >
                  <span style={{ display: '-webkit-box', overflow: 'hidden', WebkitBoxOrient: 'vertical', WebkitLineClamp: 3 }}>
                    {details.name}
                  </span>
                </button>
              </Tooltip>
            );
          })}
        </Box>
      )}
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Metadata Dictionary for Stakeholders, Risks and Solutions
// ---------------------------------------------------------------------------
const METADATA_DICTIONARY: Record<string, { role: string; persona: string; goal: string }> = {
  "PM_Kim": {
    role: "Product Manager",
    persona: "비즈니스 가치 극대화와 MVP 조기 런칭을 최우선으로 하며, 개발 공수가 늘어나는 것을 경계하는 현실적이고 속도 지향적인 리더입니다.",
    goal: "핵심 MVP 기능 위주로 빠르게 출시하여 시장을 선점하고 자율 실행 에이전트의 시장 타당성을 검증하고자 합니다."
  },
  "Arch_Park": {
    role: "Lead Architect",
    persona: "표준 MCP(Model Context Protocol) 설계와 안정적인 비동기 액션 처리를 중시하며, HWP 표 파싱의 기술적 한계와 비용을 현실적으로 평가하는 시니어 엔지니어입니다.",
    goal: "비표준 레거시 연동을 배제하고, E2E Latency 1.5초를 만족하기 위한 안정적인 분산 처리 인프라와 백아웃 정책을 검증하고자 합니다."
  },
  "Sec_Lee": {
    role: "Security Auditor",
    persona: "B2B 엔터프라이즈 환경에서 데이터 학습 방지(Zero-Retention)와 50ms 이내의 PII 개인정보 마스킹 성공률 100% 보장을 엄격하게 요구하는 컴플라이언스 전문가입니다.",
    goal: "외부 LLM 노출 시 금융권 및 대기업의 개인정보 유출 리스크를 원천 봉쇄하고, ISMS-P 및 CSAP 규제 통과 가능성을 감사합니다."
  },
  "Legal_Choi": {
    role: "Legal Counsel",
    persona: "자율형 AI 에이전트가 업무를 수행할 때 발생할 수 있는 오작동 및 고액 환불 시의 책임 소재와 데이터 소유권 귀속 규정을 보수적으로 해석하는 법률가입니다.",
    goal: "AI 오작동 시 배상 책임 계약 조항을 완비하고, HITL(상담원 개입) 결합 승인 큐를 통해 법률적 리스크가 사전에 제어되는지 평가합니다."
  },
  "CFO_Woo": {
    role: "Financial Director",
    persona: "글로벌 LLM 호출 비용 및 토큰 효율성을 감시하며, TCR(업무완결율) 지표 기반의 성과형 과금 모델 도입 시 기업의 ROI(투자수익률)를 냉철하게 추산하는 재무 전문가입니다.",
    goal: "상담 운영 비용 30% 절감 목표에 부합하는 호출 원가 모델을 수립하고, 비합리적인 대기 큐 인건비 상승이 억제되는지 따져봅니다."
  },
  "QA_Kang": {
    role: "Quality Assurance Lead",
    persona: "RAG 환각율 3% 미만 검증과 고객사 매뉴얼(HWP 등)의 오인식 방지를 위해 집요하게 엣지 케이스 시나리오와 에이전트 상담 이탈 지점을 추적하는 품질 관리 전문가입니다.",
    goal: "신뢰도 분포도가 일정 수준 이하로 떨어질 때 즉시 상담원 연결로 이탈하도록 유도하는 안전장치와 근거 기반 정확도를 검증합니다."
  },
  "SRE_Han": {
    role: "Site Reliability Engineer",
    persona: "장애 시 대체 LLM으로의 Failover 체계와 목표 SLA 99.9% 이상 유지를 위해 무중단 모니터링을 담당하는 엔프라 가용성 SRE 리더입니다.",
    goal: "서버 성능 저하 및 고도 트래픽 발생 시의 복원력을 검증하고 1.5초 이내 Latency 목표를 달성할 인프라적 방안을 요구합니다."
  },
  "Design_Jung": {
    role: "UI/UX Designer",
    persona: "대화형 승인 위젯과 톤앤매너 설정의 드래그앤드롭 편의성을 수호하며, 현업 CS 관리자의 시각적 만족도를 최우선으로 하는 미학 지향적 디자이너입니다.",
    goal: "HITL 관리자 툴의 직관적인 사용자 저니를 디자인하고 에이전트 이탈 지점이 시각적으로 즉각 모니터링되도록 보장하고자 합니다."
  },
  "FE_Han": {
    role: "Frontend Engineer",
    persona: "50ms 이내 PII 마스킹 필터링 결과물의 즉각적인 브라우저 바인딩과 실시간 대시보드 렌더링 최적화를 실무 수준에서 달성하려는 클라이언트 개발자입니다.",
    goal: "E2E Latency 1.5초를 사수하기 위한 화면 단의 최적화 기법을 완비하고, AI 신뢰도 분포도 차트의 로딩 부하를 최소화하고자 합니다."
  },
  "Sales_Oh": {
    role: "B2B Sales Lead",
    persona: "대기업/금융권 딜 클로징을 위한 규제 증명 및 세일즈 파이프라인 개방 조건을 검토하는 B2B 영업 부서 리더입니다.",
    goal: "영업 파이프라인 마비를 방지하기 위해 6월 BMT에서 기술 검증 규격을 만족하고 규제 감사 예외 증명을 획득하고자 합니다."
  },
  "HR_Seo": {
    role: "CS & HR Manager",
    persona: "AI 자동화율 40% 도달에 따른 상담원 직무 업스킬링 및 CS 노조 저항 조율을 담당하는 CS 운영 및 인사 부서 리더입니다.",
    goal: "AI 도입 시 현업 상담원들의 심리적 저항과 구조조정 불안을 완화할 내부 HR 교육 로드맵을 연계하고자 합니다."
  },
  "Seller_Min": {
    role: "Seller Representative",
    persona: "50만원 이하 자율 환불 시 셀러 대금 유출 차단 및 플랫폼 신뢰성 정산 리스크를 검증하는 입점 판매자 대변인입니다.",
    goal: "AI 오작동에 의한 셀러의 직접적 대금 손실 리스크가 없도록 책임 보전 보증과 승인 큐 개입 권한을 확보하고자 합니다."
  },
  
  // 리스크 접두사
  "Risk_PII": {
    role: "보안 리스크 (Security Risk)",
    persona: "외부 LLM 통신 시 개인식별정보(PII)가 유출되거나 Zero-Retention 협약에 위배되는 기술적 위협 요인입니다.",
    goal: "50ms 이내 마스킹 실패 시 금융 컴플라이언스 위반 및 ISMS-P 인증 통과 불가 여부를 감사합니다."
  },
  "Risk_Latency": {
    role: "성능 리스크 (Latency Risk)",
    persona: "마스킹 전처리 필터 홉(Hop) 추가 및 실시간 이벤트 렌더링 부하로 인한 E2E Latency 1.5초 돌파 위험입니다.",
    goal: "실시간 웹소켓 오버헤드와 API 게이트웨이 정체 병목을 측정하여 화면 렉을 방지하는지 평가합니다."
  },
  "Risk_SLA": {
    role: "안정성 리스크 (SLA Risk)",
    persona: "단일 LLM 장애 또는 동시 트래픽 폭증 시 백업 이중화 부재로 가용성 99.9% 보증이 무너지는 장애 위협입니다.",
    goal: "네트워크 단절 시 300ms 로컬 Ollama 엔진 전환 등 Failover 프록시 정상 작동을 보증합니다."
  },
  "Risk_Seller": {
    role: "비즈니스 리스크 (Seller Risk)",
    persona: "50만원 이하 AI 자율 환불 권한 오작동 시 입점 셀러의 정산금 오유출 및 이탈 리스크입니다.",
    goal: "AI 판정 신뢰도 임계치 설정 및 오정산 피해에 대한 플랫폼 책임 보전 합의가 타당한지 검증합니다."
  },

  // 요구사항 접두사
  "Req_FR": {
    role: "기능적 요구사항 (Functional Req)",
    persona: "50만원 이하 자율 환불(FR-01), HWP 표 파싱 RAG(FR-02), HITL 승인 큐(FR-03) 등 솔루션의 핵심 기능 명세입니다.",
    goal: "RAG 컨텍스트의 표 분석 정확도와 판단 불가 시 상담원 대기 큐 이관 로직이 무결하게 작동하는지 검증합니다."
  },
  "Req_NFR": {
    role: "비기능적 요구사항 (Non-Functional Req)",
    persona: "E2E 지연 1.5초 이내(NFR-01), Zero-Retention 아키텍처(NFR-02), 로컬 Failover(NFR-03) 등의 품질 요건입니다.",
    goal: "ISMS-P, CSAP 규제 통과를 충족하며 목표 서비스 가용성 SLA 99.9%를 유지하는지 확인합니다."
  },

  // 지표
  "Metric": {
    role: "핵심 성과 지표 (Success Metrics)",
    persona: "업무완결율(TCR) 40% 이상, 비용 30% 절감, 환각율 3% 미만 감시 등 프로젝트 성공 가이드라인입니다.",
    goal: "전문가 Swarm이 논의를 거쳐 설정한 최종 목표 지표가 기획 의도에 무결하게 도달하는지 감사합니다."
  },

  // 솔루션 접두사
  "Sol_HITL": {
    role: "아키텍처 솔루션 (HITL Solution)",
    persona: "신뢰도 85% 미만 건의 원클릭 상담원 승인/반려 모바일 UI 위젯 및 승인 대기 큐 아키텍처입니다.",
    goal: "최종 대금 인출 행위자를 인간으로 격리함으로써 AI 오작동에 대한 법률적 면책과 셀러 대금 유출 위험을 상쇄합니다."
  },
  "Sol_Shadow": {
    role: "운영 솔루션 (Shadow Testing)",
    persona: "GA 런칭 직전 4주 동안 실제 DB 수정 없이 백그라운드 모의 트래픽만 흘려 정확도 및 레이턴시를 실측하는 검증 절차입니다.",
    goal: "RAG 환각율 3% 미만 통제 상태와 CS 노조 갈등 우려를 불식시킬 상담원 직무 업스킬링 통계를 도출합니다."
  },
  "Sol_Failover": {
    role: "인프라 솔루션 (Failover Solution)",
    persona: "외부 LLM 마비 시 300ms 이내에 로컬 Ollama 엔진으로 자동 스위칭하는 이중화 프록시 가용 체계입니다.",
    goal: "SRE 관점의 SLA 99.9% 목표 수호와 호출 토큰비 30% ROI 절감 모델의 실현 가능성을 입증합니다."
  },

  // 프로젝트 마일스톤 및 시스템 모듈
  "Milestone": {
    role: "배포 마일스톤 (Milestone)",
    persona: "6월 BMT 기술 검증 통과 및 9월 정식 GA 출시를 달성하기 위한 개발 프로젝트 로드맵 이정표입니다.",
    goal: "시뮬레이션 합의 체계 완성 상태를 바탕으로 차기 2차 파이프라인 개방 조건 만족 여부를 검증합니다."
  },
  "Sys": {
    role: "시스템 컴포넌트 (System)",
    persona: "로컬 Ollama 엔진, API Gateway, PII 필터링 및 RAG 벡터 DB 등 Simply AI Agent 아키텍처를 구성하는 물리 모듈입니다.",
    goal: "각 모듈 간의 통신 병목 및 데이터 프라이버시 침해 지점을 감시하고 이중화 안정성을 검증합니다."
  }
};

export function SimulationRunner({ performAction, sessionId }: Props) {
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], links: [] });
  const [logs, setLogs] = useState<EventLog[]>([]);
  const [progress, setProgress] = useState(0);
  const [isSimulationComplete, setIsSimulationComplete] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const logsEndRef = useRef<HTMLDivElement>(null);

  // ── Node & Link Selection State for Filtering ─────────────────────────
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedLinkId, setSelectedLinkId] = useState<string | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [simulationMode, setSimulationMode] = useState<'mock' | 'live' | 'live_llm' | 'live_fallback' | 'live_error' | null>(null);


  // ── Dynamic Visualization Controls State ───────────────────────────────
  const [nodeSize, setNodeSize] = useState(8);
  const [sliderLinkWidth, setSliderLinkWidth] = useState(1.2);
  const [clusterDistance, setClusterDistance] = useState(0.24);
  const [isSettingPanelOpen, setIsSettingPanelOpen] = useState(true);
  const [showBottomLog, setShowBottomLog] = useState(true);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [simulationReason, setSimulationReason] = useState<string | null>(null);
  const bottomLogEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        const { clientHeight: height, clientWidth: width } = containerRef.current;
        if (width <= 0 || height <= 0) return;

        setDimensions(() => ({
          width,
          height,
        }));
      }
    };

    updateDimensions();
    const resizeObserver = new ResizeObserver(updateDimensions);
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    return () => {
      resizeObserver.disconnect();
    };
  }, []);

  // dimensions는 리사이즈마다 새 객체가 되므로, SSE 구독 effect가 이를
  // 의존성으로 두면 창 크기를 바꿀 때마다 스트림이 재연결되어 시뮬레이션이
  // 처음부터 다시 시작된다. ref로 최신 값만 읽어 재구독을 막는다.
  const dimensionsRef = useRef(dimensions);
  useEffect(() => {
    dimensionsRef.current = dimensions;
  }, [dimensions]);

  // Initialize new nodes with clustered starting positions to jump-start clustering
  useEffect(() => {
    if (graphData.nodes && graphData.nodes.length > 0) {
      const centerX = dimensions.width / 2;
      const centerY = dimensions.height / 2;
      const radius = Math.min(dimensions.width, dimensions.height) * clusterDistance;
      
      graphData.nodes.forEach((node: GraphNode) => {
        if (node.x === undefined || node.y === undefined) {
          const group = node.group || 0;
          const angle = (group / 7) * 2 * Math.PI;
          
          const crossGroupLinks = graphData.links.filter((l: GraphLink) => {
            const sId = getEndpointId(l.source);
            const tId = getEndpointId(l.target);
            if (sId !== node.id && tId !== node.id) return false;
            const otherId = sId === node.id ? tId : sId;
            const otherNode = graphData.nodes.find(n => n.id === otherId);
            return otherNode && otherNode.group !== group;
          });
          const crossCount = crossGroupLinks.length;
          
          const clusterX = centerX + radius * Math.cos(angle);
          const clusterY = centerY + radius * Math.sin(angle);
          
          let initX = clusterX;
          let initY = clusterY;
          
          if (crossCount >= 1) {
            const weight = Math.min(0.25 + crossCount * 0.08, 0.70);
            initX = clusterX * (1 - weight) + centerX * weight;
            initY = clusterY * (1 - weight) + centerY * weight;
          } else {
            const pushFactor = 1.15;
            initX = centerX + (clusterX - centerX) * pushFactor;
            initY = centerY + (clusterY - centerY) * pushFactor;
          }
          
          node.x = initX + (Math.random() - 0.5) * 45;
          node.y = initY + (Math.random() - 0.5) * 45;
        }
      });
    }
  }, [graphData, dimensions, clusterDistance]);



  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    bottomLogEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  useEffect(() => {
    const eventSource = new EventSource(`/api/simulation/stream?session_id=${encodeURIComponent(sessionId)}`);
    // 언마운트 시 남은 카메라 정렬 타이머를 정리하기 위해 추적한다.
    const pendingTimeouts: ReturnType<typeof setTimeout>[] = [];

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setStreamError(null);
        
        if (data.mode) {
          setSimulationMode(data.mode);
        }
        if (data.reason) {
          setSimulationReason(data.reason);
        }

        if (data.type === 'mode_check') {
          return;
        }

        if (data.type === 'simulation_complete') {
          eventSource.close();
          setProgress(100);
          setIsSimulationComplete(true);
          return;
        }

        if (data.type === 'simulation_error') {
          eventSource.close();
          setStreamError(data.content || data.reason || 'Live simulation failed.');
          return;
        }

        if (data.progress !== undefined) {
          setProgress(data.progress * 100);
        }

        // 실시간 노드/링크 동기화: 페이로드에 nodes와 links가 존재하면 즉시 그래프 데이터 갱신
        if (data.nodes && Array.isArray(data.nodes) && data.links && Array.isArray(data.links)) {
          const isInitialLoad = graphData.nodes.length === 0;

          setGraphData(prev => {
            const prevCoordsMap = new Map<string, NodeObject>();
            const prevBirthMap = new Map<string, number>();
            const sourceNodes = prev?.nodes || [];

            sourceNodes.forEach((n: GraphNode) => {
              if (n.x !== undefined && n.y !== undefined) {
                prevCoordsMap.set(n.id, { x: n.x, y: n.y, vx: n.vx, vy: n.vy, fx: n.fx, fy: n.fy });
              }
              if (n.birthTime !== undefined) {
                prevBirthMap.set(n.id, n.birthTime);
              }
            });

            // 2. 새 노드 리스트에 좌표 복제 및 birthTime 설정
            const updatedNodes = data.nodes.map((node: GraphNode) => {
              const coords = prevCoordsMap.get(node.id);
              const prevBirth = prevBirthMap.get(node.id);
              const birthTime = prevBirth !== undefined ? prevBirth : Date.now();
              if (coords) {
                return {
                  ...node,
                  x: coords.x,
                  y: coords.y,
                  vx: coords.vx,
                  vy: coords.vy,
                  fx: coords.fx,
                  fy: coords.fy,
                  birthTime
                };
              }
              return {
                ...node,
                birthTime
              };
            });

            // 기존 링크들의 birthTime 맵핑
            const prevLinkBirthMap = new Map<string, number>();
            if (prev && prev.links) {
              prev.links.forEach((l: GraphLink) => {
                const sId = getEndpointId(l.source);
                const tId = getEndpointId(l.target);
                if (!sId || !tId) return;
                const lKey = `${sId}-${tId}`;
                if (l.birthTime !== undefined) {
                  prevLinkBirthMap.set(lKey, l.birthTime);
                }
              });
            }

            // 3. 새 링크 리스트에 실제 노드 객체 레퍼런스 이식 및 birthTime 설정
            const nodeIds = new Set(updatedNodes.map((node: GraphNode) => node.id));
            const updatedLinks = data.links.flatMap((link: GraphLink) => {
              const sId = getEndpointId(link.source);
              const tId = getEndpointId(link.target);
              if (!sId || !tId || !nodeIds.has(sId) || !nodeIds.has(tId)) return [];

              const sourceNode = updatedNodes.find((n: GraphNode) => n.id === sId);
              const targetNode = updatedNodes.find((n: GraphNode) => n.id === tId);
              
              const lKey = `${sId}-${tId}`;
              const prevBirth = prevLinkBirthMap.get(lKey);
              const birthTime = prevBirth !== undefined ? prevBirth : Date.now();

              return [{
                ...link,
                source: sourceNode || sId,
                target: targetNode || tId,
                birthTime
              }];
            });

            return { nodes: updatedNodes, links: updatedLinks };
          });

          void isInitialLoad;
        } else if (data.type === 'graph_update') {
          // Fallback dummy node generator (ontology 데이터가 없을 때의 안전장치)
          const timestamp = Date.now();
          const newNodes = [
            { id: `node_${timestamp}_0`, group: Math.floor(Math.random() * 3) },
            { id: `node_${timestamp}_1`, group: Math.floor(Math.random() * 3) },
            { id: `node_${timestamp}_2`, group: Math.floor(Math.random() * 3) }
          ];
          
          const animatedNewNodes = newNodes.map(node => ({ ...node, birthTime: Date.now() }));
          setGraphData(prev => {
            if (prev.nodes.length === 0) {
              return { nodes: animatedNewNodes, links: [] };
            }
            const newLinks = [
              { source: (prev.nodes[Math.floor(Math.random() * prev.nodes.length)])?.id || 'node_0', target: animatedNewNodes[0].id, birthTime: Date.now() },
              { source: animatedNewNodes[0].id, target: animatedNewNodes[1].id, birthTime: Date.now() },
              { source: animatedNewNodes[1].id, target: animatedNewNodes[2].id, birthTime: Date.now() },
              { source: animatedNewNodes[2].id, target: (prev.nodes[Math.floor(Math.random() * prev.nodes.length)])?.id || 'node_1', birthTime: Date.now() }
            ];
            return {
              nodes: [...prev.nodes, ...animatedNewNodes],
              links: [...prev.links, ...newLinks]
            };
          });
        }

        setLogs(prev => [...prev, data]);
      } catch (e) {
        console.error('Error parsing SSE', e);
      }
    };

    eventSource.onerror = () => {
      eventSource.close();
      setStreamError('시뮬레이션 연결이 끊어졌습니다. 저장된 결과를 확인하거나 새 실행을 시작해주세요.');
    };

    return () => {
      eventSource.close();
      pendingTimeouts.forEach(clearTimeout);
    };
    // 의도적으로 빈 배열: 스트림은 마운트 시 1회만 구독한다. 최신 dimensions는
    // dimensionsRef로 읽으며, performAction은 이 effect 안에서 쓰이지 않는다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Node & Link interactive handlers ───────────────────────────────────
  const handleNodeClick = (node: GraphNode) => {
    setSelectedLinkId(null); // Clear link filter
    setSelectedNodeId(prev => prev === node.id ? null : node.id);
  };

  const getNodeDetails = (node: GraphNode): NodeDetails => {
    let role = node.role;
    let persona = node.summary || node.persona;
    let goal = node.goal;
    
    if (!role || !persona || !goal) {
      let meta = METADATA_DICTIONARY[node.id];
      if (!meta) {
        const nodeId = node.id || "";
        const matchedKey = Object.keys(METADATA_DICTIONARY).find(key => 
          nodeId.startsWith(key) || nodeId.includes(key) || key.includes(nodeId)
        );
        if (matchedKey) {
          meta = METADATA_DICTIONARY[matchedKey];
        }
      }
      
      if (meta) {
        role = role || meta.role;
        persona = persona || meta.persona;
        goal = goal || meta.goal;
      }
    }
    
    role = role || "이해관계자";
    persona = persona || "Simply AI Agent PRD 시뮬레이션의 검증 노드입니다.";
    goal = goal || "PRD 요구사항 적합성 및 안정성 검증";
    
    const name = node.label || node.id;
    
    return { name, role, persona, goal };
  };

  // ── Filtered Dialogue Feed ─────────────────────────────────────────────
  const getFilteredLogs = () => {
    const result = logs.filter(log => {
      if (log.type !== 'agent_post') return false;
      
      if (selectedNodeId) {
        const selectedNode = graphData.nodes.find(n => n.id === selectedNodeId);
        if (!selectedNode) return false;
        const nodeName = selectedNode.label || selectedNode.id;
        const isAgentMatch = log.agent_name === nodeName || 
                             log.agent_name?.includes(nodeName) || 
                             nodeName.includes(log.agent_name || '');
                             
        const isMentioned = log.content?.toLowerCase().includes(nodeName.toLowerCase()) || 
                            log.content?.toLowerCase().includes(selectedNode.id.toLowerCase()) ||
                            (nodeName.length > 3 && log.content?.toLowerCase().includes(nodeName.substring(0, 4).toLowerCase()));
                            
        const connectedNodeIds = graphData.links
          .filter(l => {
            const sId = getEndpointId(l.source);
            const tId = getEndpointId(l.target);
            return sId === selectedNodeId || tId === selectedNodeId;
          })
          .map(l => {
            const sId = getEndpointId(l.source);
            const tId = getEndpointId(l.target);
            return sId === selectedNodeId ? tId : sId;
          });
        
        const isConnectedAgentMatch = connectedNodeIds.some(cId => {
          const cNode = graphData.nodes.find(n => n.id === cId);
          if (!cNode) return false;
          const cName = cNode.label || cNode.id;
          return log.agent_name === cName || log.agent_name?.includes(cName) || cName.includes(log.agent_name || '');
        });

        // 4) 키워드 매핑 사전 기반 매칭
        const TOPIC_KEYWORDS: Record<string, string[]> = {
          "pii": ["pii", "개인정보", "마스킹", "보안", "필터", "유출", "retention", "감사", "공개", "저장", "isms"],
          "latency": ["latency", "지연", "속도", "시간", "초", "렉", "웹소켓", "성능", "대시보드", "응답"],
          "sla": ["sla", "가용성", "failover", "장애", "프록시", "ollama", "이중화", "가동", "무중단"],
          "seller": ["셀러", "정산", "판매자", "대금", "환불", "오환불", "손실", "이탈", "수수료"],
          "fr": ["fr", "기능", "환불", "hwp", "파서", "표", "셀", "hitl", "대기", "승인", "취소", "조회"],
          "nfr": ["nfr", "지연", "속도", "retention", "보안", "failover", "ollama", "대체", "isms"],
          "metric": ["tcr", "완결", "비용", "절감", "원가", "환각", "정확도", "지표", "목표"],
          "hitl": ["hitl", "승인", "대기", "큐", "위젯", "알림톡", "상담원", "개입", "판정", "감사관"],
          "shadow": ["shadow", "섀도우", "테스트", "모의", "실측", "검증", "노조", "교육", "훈련", "업스킬링"],
          "failover": ["failover", "ollama", "프록시", "이중화", "장애", "원가", "비용", "서버", "우회"]
        };

        const matchedKeywords = Object.keys(TOPIC_KEYWORDS)
          .filter(key => selectedNode.id.toLowerCase().includes(key) || nodeName.toLowerCase().includes(key))
          .flatMap(key => TOPIC_KEYWORDS[key]);
        
        const isKeywordMatch = matchedKeywords.some(kw => 
          log.content?.toLowerCase().includes(kw)
        );

        return isAgentMatch || isMentioned || isConnectedAgentMatch || isKeywordMatch;
      }
      
      if (selectedLinkId) {
        const [sourceId, targetId] = selectedLinkId.split('-');
        const sourceNode = graphData.nodes.find(n => n.id === sourceId);
        const targetNode = graphData.nodes.find(n => n.id === targetId);
        if (!sourceNode || !targetNode) return false;
        const sourceName = sourceNode.label || sourceNode.id;
        const targetName = targetNode.label || targetNode.id;
        return log.agent_name === sourceName || log.agent_name === targetName ||
               log.agent_name?.includes(sourceName) || log.agent_name?.includes(targetName);
      }
      
      return true;
    });

    // Fallback: 1차 필터링 결과가 없고 특정 노드를 누른 경우 노드 그룹 연관 대화 필터링
    if (selectedNodeId && result.length === 0) {
      const selectedNode = graphData.nodes.find(n => n.id === selectedNodeId);
      if (selectedNode) {
        const nodeGroup = selectedNode.group;
        return logs.filter(log => {
          if (log.type !== 'agent_post') return false;
          
          if (nodeGroup === 0) {
            const roles = ["product manager", "pm", "architect", "engineer", "designer", "frontend", "backend"];
            const isRoleMatch = roles.some(r => log.agent_type?.toLowerCase().includes(r));
            const hasKeyword = ["기획", "개발", "화면", "디자인", "아키텍트", "코드"].some(k => log.content?.includes(k));
            return isRoleMatch || hasKeyword;
          }
          if (nodeGroup === 1) {
            const roles = ["security", "auditor", "legal", "counsel", "lawyer"];
            const isRoleMatch = roles.some(r => log.agent_type?.toLowerCase().includes(r));
            const hasKeyword = ["보안", "규격", "규제", "법무", "계약", "개인정보", "pii", "컴플라이언스"].some(k => log.content?.includes(k));
            return isRoleMatch || hasKeyword;
          }
          if (nodeGroup === 2) {
            const roles = ["financial", "cfo", "analyst", "qa", "test", "sre", "reliability"];
            const isRoleMatch = roles.some(r => log.agent_type?.toLowerCase().includes(r));
            const hasKeyword = ["비용", "예산", "재무", "장애", "테스트", "통계", "가용성", "서버"].some(k => log.content?.includes(k));
            return isRoleMatch || hasKeyword;
          }
          if (nodeGroup === 3) {
            const roles = ["sales", "hr", "manager", "seller", "representative"];
            const isRoleMatch = roles.some(r => log.agent_type?.toLowerCase().includes(r));
            const hasKeyword = ["영업", "노조", "상담원", "셀러", "정산", "이탈", "고객"].some(k => log.content?.includes(k));
            return isRoleMatch || hasKeyword;
          }
          if (nodeGroup === 4) {
            const keywords = ["위험", "리스크", "우려", "장애", "유출", "지연", "정체", "오환불", "피해", "이탈"];
            return keywords.some(k => log.content?.includes(k));
          }
          if (nodeGroup === 5) {
            const keywords = ["해결", "솔루션", "대안", "hitl", "승인 큐", "알림톡", "위젯", "섀도우", "shadow", "failover", "ollama", "업스킬링", "스피너"];
            return keywords.some(k => log.content?.includes(k));
          }
          if (nodeGroup === 6) {
            const keywords = ["마일스톤", "합의", "출시", "런칭", "bmt", "정식", "완성", "consensus"];
            const isConclusion = log.agent_name === "PM 김철수" || log.agent_type?.includes("Product Manager");
            return keywords.some(k => log.content?.includes(k)) || isConclusion;
          }
          return true;
        });
      }
    }
    return result;
  };
  const filteredLogs = getFilteredLogs();

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, minWidth: 0, width: '100%' }}>
    <div style={{ flex: 1, display: 'flex', minHeight: 0, minWidth: 0 }}>
      {/* Network Graph Area */}
      <div ref={containerRef} style={{ flex: 2, minWidth: 0, background: 'var(--bg-app)', position: 'relative' }}>
        <GraphErrorBoundary>
        <SimulationNodeGraph
          nodes={graphData.nodes}
          links={graphData.links}
          selectedNodeId={selectedNodeId}
          hoveredNodeId={hoveredNodeId}
          onNodeClick={handleNodeClick}
          onNodeHover={(node) => setHoveredNodeId(node ? node.id : null)}
          nodeDetails={getNodeDetails}
          nodeSize={nodeSize}
        />
        </GraphErrorBoundary>
        
        {/* Visualization Controller Panel */}
        <Paper
          shadow="md"
          p="sm"
          withBorder
          style={{
            position: 'absolute',
            top: 110,
            left: 20,
            background: 'rgba(9, 13, 22, 0.95)',
            borderColor: 'rgba(255, 255, 255, 0.08)',
            backdropFilter: 'blur(10px)',
            zIndex: 10,
            width: '280px',
            color: '#f8fafc',
            pointerEvents: 'auto'
          }}
        >
          <Group justify="space-between" mb={isSettingPanelOpen ? 'xs' : 0}>
            <Text fw={800} size="xs" c="cyan.4" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              시각화 설정
            </Text>
            <Button 
              size="xs"
              variant="subtle"
              color="gray"
              onClick={() => setIsSettingPanelOpen(!isSettingPanelOpen)}
              styles={{ root: { padding: '2px 6px', height: 'auto' } }}
            >
              {isSettingPanelOpen ? '접기' : '조절하기'}
            </Button>
          </Group>

          {isSettingPanelOpen && (
            <Stack gap="xs" style={{ fontSize: '0.7rem' }}>
              {/* Node Size Slider */}
              <Box>
                <Group justify="space-between" mb={3}>
                  <Text size="xs" c="dimmed">노드 크기 (Node Size)</Text>
                  <Text size="xs" fw={700} c="cyan.4">{nodeSize}px</Text>
                </Group>
                <Slider 
                  min={4}
                  max={18}
                  step={1}
                  value={nodeSize}
                  onChange={setNodeSize}
                  size="xs"
                  color="cyan"
                />
              </Box>

              {/* Link Thickness Slider */}
              <Box>
                <Group justify="space-between" mb={3}>
                  <Text size="xs" c="dimmed">링크 굵기 (Link Thickness)</Text>
                  <Text size="xs" fw={700} c="cyan.4">{sliderLinkWidth}px</Text>
                </Group>
                <Slider 
                  min={0.5}
                  max={5.0}
                  step={0.1}
                  value={sliderLinkWidth}
                  onChange={setSliderLinkWidth}
                  size="xs"
                  color="cyan"
                />
              </Box>

              {/* Cluster Distance Slider */}
              <Box>
                <Group justify="space-between" mb={3}>
                  <Text size="xs" c="dimmed">군집 거리 (Cluster Distance)</Text>
                  <Text size="xs" fw={700} c="cyan.4">{clusterDistance.toFixed(2)}</Text>
                </Group>
                <Slider 
                  min={0.10}
                  max={0.80}
                  step={0.02}
                  value={clusterDistance}
                  onChange={setClusterDistance}
                  size="xs"
                  color="cyan"
                />
              </Box>
            </Stack>
          )}
        </Paper>
        
        {/* Graph Legend Panel */}
        <Paper
          shadow="md"
          p="sm"
          withBorder
          style={{ 
            position: 'absolute', 
            bottom: 80, 
            left: 20, 
            background: 'rgba(9, 13, 22, 0.95)', 
            borderColor: 'rgba(255, 255, 255, 0.08)',
            backdropFilter: 'blur(8px)', 
            zIndex: 10,
            width: '280px',
            pointerEvents: 'auto'
          }}
        >
          <Text fw={700} size="xs" mb="xs" c="white">역할군(Group) 범례</Text>
          <Stack gap={6}>
            <Group gap="xs" wrap="nowrap">
              <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: '#3b82f6', flexShrink: 0 }}></span>
              <Text size="10px" c="dimmed">기획 및 개발 (Group 0) - PM, 아키텍트 등</Text>
            </Group>
            <Group gap="xs" wrap="nowrap">
              <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: '#10b981', flexShrink: 0 }}></span>
              <Text size="10px" c="dimmed">보안 및 규제 (Group 1) - 감사관, 법무팀장</Text>
            </Group>
            <Group gap="xs" wrap="nowrap">
              <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: '#eab308', flexShrink: 0 }}></span>
              <Text size="10px" c="dimmed">재무, SRE, QA (Group 2) - CFO, QA, SRE</Text>
            </Group>
            <Group gap="xs" wrap="nowrap">
              <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: '#a855f7', flexShrink: 0 }}></span>
              <Text size="10px" c="dimmed">현업 및 생태계 (Group 3) - 영업, HR, 셀러</Text>
            </Group>
            <Group gap="xs" wrap="nowrap">
              <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: '#ef4444', flexShrink: 0 }}></span>
              <Text size="10px" c="dimmed">도출된 리스크 (Group 4) - 보안/재무/정산</Text>
            </Group>
            <Group gap="xs" wrap="nowrap">
              <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: '#f97316', flexShrink: 0 }}></span>
              <Text size="10px" c="dimmed">대안 및 솔루션 (Group 5) - HITL, 섀도우모드</Text>
            </Group>
            <Group gap="xs" wrap="nowrap">
              <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: '#64748b', flexShrink: 0 }}></span>
              <Text size="10px" c="dimmed">출시 마일스톤 (Group 6) - 런칭 목표</Text>
            </Group>
          </Stack>
        </Paper>
 
        <Paper
          shadow="md"
          p="sm"
          withBorder
          style={{ 
            position: 'absolute', 
            top: 20, 
            left: 20, 
            background: 'rgba(9, 13, 22, 0.95)', 
            borderColor: 'rgba(255, 255, 255, 0.08)',
            backdropFilter: 'blur(6px)', 
            zIndex: 10 
          }}
        >
          <Group gap="xs" mb={4}>
            <Text fw={800} size="sm" c="white">Simulation Network</Text>
            {simulationMode && (
              <Badge 
                color={simulationMode === 'live' || simulationMode === 'live_llm' ? 'green' : simulationMode === 'live_fallback' || simulationMode === 'live_error' ? 'red' : 'yellow'}
                variant="light" 
                size="xs"
              >
                {simulationMode === 'live'
                  ? 'MiroFish Live'
                  : simulationMode === 'live_llm'
                    ? 'Live LLM'
                    : simulationMode === 'live_error'
                      ? 'Live Failed'
                      : simulationMode === 'live_fallback'
                        ? 'Live Fallback'
                        : 'Mock Mode'}
              </Badge>
            )}
          </Group>
          <Text size="xs" c="dimmed">Nodes: {graphData.nodes.length} | Links: {graphData.links.length}</Text>
          {simulationMode && (
            <Text size="xs" c={simulationMode === 'live' || simulationMode === 'live_llm' ? 'teal.3' : 'yellow.3'} mt={4}>
              {simulationMode === 'live'
                ? '실제 MiroFish 엔진 이벤트를 표시하고 있습니다.'
                : simulationMode === 'live_llm'
                  ? '구성된 LLM API가 현재 PRD와 Reality Seeds를 바탕으로 생성한 Live 시뮬레이션입니다.'
                  : simulationMode === 'live_error'
                    ? 'Live 호출이 실패했습니다. Mock 결과로 대체하지 않았습니다.'
                    : '현재 PRD와 Reality Seeds를 입력으로 한 로컬 Mock 시뮬레이션입니다.'}
            </Text>
          )}
          {simulationReason && <Text size="xs" c="orange.3" mt={4}>{simulationReason}</Text>}
          {streamError && <Text size="xs" c="red.4" mt={4}>{streamError}</Text>}
        </Paper>

        {/* Bottom Log Panel Toggle */}
        <Button
          size="xs"
          variant="subtle"
          color={showBottomLog ? 'teal' : 'gray'}
          onClick={() => setShowBottomLog(prev => !prev)}
          leftSection={<span style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            backgroundColor: showBottomLog ? '#10b981' : '#94a3b8',
            boxShadow: showBottomLog ? '0 0 8px #10b981' : 'none'
          }} />}
          style={{ position: 'absolute', top: 20, right: 20, zIndex: 10, pointerEvents: 'auto' }}
          styles={{
            root: {
              background: 'rgba(9, 13, 22, 0.95)',
              border: showBottomLog ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(255, 255, 255, 0.08)',
              backdropFilter: 'blur(6px)',
            }
          }}
        >
          하단 로그 {showBottomLog ? 'ON' : 'OFF'}
        </Button>

        <Box style={{ position: 'absolute', bottom: 20, left: 20, right: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', pointerEvents: 'none' }}>
            <Box style={{ flex: 1, marginRight: '2rem', pointerEvents: 'auto' }}>
                <Progress
                  value={progress}
                  size="xs"
                  radius="xl"
                  animated={progress < 100}
                  color="indigo"
                />
                <Text size="10px" c="dimmed" mt={4}>
                    {progress >= 100 ? 'Simulation Complete' : `Running... ${Math.round(progress)}%`}
                </Text>
            </Box>
 
            {isSimulationComplete && (
              <Button 
                variant="gradient"
                gradient={{ from: 'indigo', to: 'cyan' }}
                onClick={() => void performAction('simulation_complete')}
                style={{ pointerEvents: 'auto', whiteSpace: 'nowrap' }}
              >
                View Simulation Report →
              </Button>
            )}
        </Box>
      </div>

      {/* Real-time Feeds Array */}
      <Box style={{ flex: 1, borderLeft: '1px solid var(--border)', background: 'var(--bg-panel)', display: 'flex', flexDirection: 'column' }}>
        <Group justify="space-between" p="sm" style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.08)', background: 'rgba(9, 13, 22, 0.85)' }}>
            <Text fw={700} size="sm" c="white">Live Feed</Text>
            {(selectedNodeId || selectedLinkId) && (
              <Group gap="xs">
                <Badge size="xs" variant="outline" color="cyan">
                  {selectedNodeId ? `필터: ${METADATA_DICTIONARY[selectedNodeId]?.role || selectedNodeId}` : '필터: 연결선'}
                </Badge>
                <Button 
                  size="xs"
                  color="red"
                  variant="light"
                  onClick={() => { setSelectedNodeId(null); setSelectedLinkId(null); }}
                  styles={{ root: { padding: '2px 6px', height: 'auto' } }}
                >
                  전체 보기
                </Button>
              </Group>
            )}
        </Group>
        
        <ScrollArea style={{ flex: 1, padding: '16px' }}>
          <Stack gap="sm">
            {filteredLogs.length === 0 ? (
              <Text size="xs" c="dimmed" ta="center" mt="xl">
                해당 주체의 발언 내역이 없습니다.
              </Text>
            ) : (
              filteredLogs.map((log, i) => (
                <Paper
                  key={i}
                  p="xs"
                  radius="sm"
                  className="feed-item-animate"
                  bg={log.type === 'agent_post' ? 'rgba(255, 255, 255, 0.02)' : 'transparent'}
                  style={{
                    border: log.type === 'agent_post' ? '1px solid rgba(255, 255, 255, 0.05)' : 'none'
                  }}
                >
                  {log.type === 'agent_post' && (
                    <>
                      <Group gap="xs" mb={4}>
                        <Text size="xs" fw={700} c="cyan.4">{log.agent_name}</Text>
                        <Text size="10px" c="dimmed">({log.agent_type})</Text>
                        {log.round && <Badge size="xs" variant="light" color="violet">Round {log.round}</Badge>}
                      </Group>
                      {log.reply_to && (
                        <Text size="10px" c="violet.3" mb={4}>
                          ↳ {log.reply_to === 'topic' ? '시뮬레이션 주제' : log.reply_to}의 주장에 {log.stance === 'challenge' ? '반박' : log.stance === 'support' ? '지지' : '절충안 제시'}: {log.claim_reference || '이전 발언'}
                        </Text>
                      )}
                    </>
                  )}
                  <Text size="xs" style={{ color: log.type === 'agent_post' ? '#cbd5e1' : '#64748b' }}>
                    {log.content || log.message}
                  </Text>
                  {log.timestamp && (
                    <Text size="9px" c="dimmed" mt={4} ta="right">
                      {new Date(log.timestamp).toLocaleTimeString()}
                    </Text>
                  )}
                </Paper>
              ))
            )}
            <div ref={logsEndRef} />
          </Stack>
        </ScrollArea>
      </Box>
    </div>

    {showBottomLog && (
      <Box style={{
        height: 220,
        flexShrink: 0,
        borderTop: '1px solid var(--border)',
        background: 'var(--bg-panel)',
        display: 'flex',
        flexDirection: 'column'
      }}>
        <Group justify="space-between" p="sm" style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.08)', background: 'rgba(9, 13, 22, 0.85)', flexShrink: 0 }}>
          <Group gap="xs">
            <Text fw={700} size="sm" c="white">Simulation Log</Text>
            <Badge size="xs" variant="outline" color="teal">{logs.length} events</Badge>
          </Group>
          <Button
            size="xs"
            variant="subtle"
            color="gray"
            onClick={() => setShowBottomLog(false)}
            styles={{ root: { padding: '2px 6px', height: 'auto' } }}
          >
            숨기기
          </Button>
        </Group>
        <ScrollArea style={{ flex: 1, padding: '8px 16px' }}>
          <Stack gap={4}>
            {logs.length === 0 ? (
              <Text size="xs" c="dimmed" ta="center" mt="md">
                아직 수신된 로그가 없습니다.
              </Text>
            ) : (
              logs.map((log, i) => (
                <Group key={i} gap="xs" wrap="nowrap" align="flex-start" style={{ fontFamily: 'monospace' }}>
                  {log.timestamp && (
                    <Text size="9px" c="dimmed" style={{ flexShrink: 0, whiteSpace: 'nowrap' }}>
                      {new Date(log.timestamp).toLocaleTimeString()}
                    </Text>
                  )}
                  <Badge size="xs" variant="light" color={log.type === 'agent_post' ? 'cyan' : log.type === 'simulation_complete' ? 'green' : 'gray'} style={{ flexShrink: 0 }}>
                    {log.type}
                  </Badge>
                  {log.agent_name && (
                    <Text size="10px" fw={700} c="cyan.4" style={{ flexShrink: 0 }}>{log.agent_name}</Text>
                  )}
                  <Text size="10px" c="dimmed" style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                    {log.content || log.message || ''}
                  </Text>
                </Group>
              ))
            )}
            <div ref={bottomLogEndRef} />
          </Stack>
        </ScrollArea>
      </Box>
    )}
    </div>
  );
}
