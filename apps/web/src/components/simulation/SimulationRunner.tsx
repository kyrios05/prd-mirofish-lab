import { useEffect, useState, useRef } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { forceX, forceY, forceCollide } from 'd3-force';

interface Props {
  performAction: (actionId: string, payload?: any) => Promise<void>;
}

interface EventLog {
  type: string;
  timestamp: string;
  message?: string;
  agent_name?: string;
  agent_type?: string;
  content?: string;
}

interface GraphNode {
  id: string;
  group: number;
  label?: string;
}

interface GraphLink {
  source: any;
  target: any;
}

interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
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

export function SimulationRunner({ performAction }: Props) {
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], links: [] });
  const [logs, setLogs] = useState<EventLog[]>([]);
  const [progress, setProgress] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const logsEndRef = useRef<HTMLDivElement>(null);

  // ── Node & Link Selection State for Filtering ─────────────────────────
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedLinkId, setSelectedLinkId] = useState<string | null>(null);
  const [simulationMode, setSimulationMode] = useState<'mock' | 'live' | 'live_fallback' | null>(null);
  const fgRef = useRef<any>(null);

  useEffect(() => {
    if (containerRef.current) {
      setDimensions({
        width: containerRef.current.clientWidth,
        height: containerRef.current.clientHeight
      });
    }

    const handleResize = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight
        });
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Initialize new nodes with clustered starting positions to jump-start clustering
  useEffect(() => {
    if (graphData.nodes && graphData.nodes.length > 0) {
      const centerX = dimensions.width / 2;
      const centerY = dimensions.height / 2;
      const radius = Math.min(dimensions.width, dimensions.height) * 0.35;
      
      graphData.nodes.forEach((node: any) => {
        if (node.x === undefined || node.y === undefined) {
          const group = node.group || 0;
          const angle = (group / 7) * 2 * Math.PI;
          node.x = centerX + radius * Math.cos(angle) + (Math.random() - 0.5) * 60;
          node.y = centerY + radius * Math.sin(angle) + (Math.random() - 0.5) * 60;
        }
      });
    }
  }, [graphData, dimensions]);

  // Configure Force Layout Clustering
  useEffect(() => {
    if (fgRef.current) {
      const fg = fgRef.current;
      try {
        // 1. Center force 제거 (노드들이 한 군데 뭉치는 주범)
        fg.d3Force('center', null);

        // 2. Link force의 강도와 거리 조율
        fg.d3Force('link')
          ?.distance(35)
          ?.strength(0.4);

        // 3. Repulsion (서로 밀어내는 힘) 강하게 적용
        fg.d3Force('charge')?.strength(-160);

        // 4. Group 기반 중심 좌표 유도 force
        const centerX = dimensions.width / 2;
        const centerY = dimensions.height / 2;
        const radius = Math.min(dimensions.width, dimensions.height) * 0.35;

        fg.d3Force('x', forceX().x((d: any) => {
          const group = d.group || 0;
          const angle = (group / 7) * 2 * Math.PI;
          return centerX + radius * Math.cos(angle);
        }).strength(0.35));

        fg.d3Force('y', forceY().y((d: any) => {
          const group = d.group || 0;
          const angle = (group / 7) * 2 * Math.PI;
          return centerY + radius * Math.sin(angle);
        }).strength(0.35));

        // 5. Collision 힘 (노드가 겹치지 않게)
        fg.d3Force('collide', forceCollide().radius(20));

        fg.d3ReheatSimulation();
      } catch (err) {
        console.error("Failed to configure D3 force layout clustering:", err);
      }
    }
  }, [fgRef, dimensions, graphData]);


  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  useEffect(() => {
    // Generate initial dummy graph
    const nodes = Array.from({ length: 15 }).map((_, i) => ({ id: `node_${i}`, group: Math.floor(Math.random() * 3) }));
    const links = Array.from({ length: 20 }).map(() => ({
      source: `node_${Math.floor(Math.random() * 15)}`,
      target: `node_${Math.floor(Math.random() * 15)}`
    }));
    setGraphData({ nodes, links } as any);

    const eventSource = new EventSource('/api/simulation/stream');
    
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.mode) {
          setSimulationMode(data.mode);
        }

        if (data.type === 'mode_check') {
          return;
        }

        if (data.type === 'simulation_complete') {
          eventSource.close();
          setProgress(100);
          return;
        }

        if (data.progress !== undefined) {
          setProgress(data.progress * 100);
        }

        if (data.type === 'graph_update') {
          // 1. If backend provides real ontology graph data, prioritize binding it
          if (data.nodes && Array.isArray(data.nodes) && data.links && Array.isArray(data.links)) {
            setGraphData({ nodes: data.nodes, links: data.links });
          } else {
            // 2. High-density Mesh Network algorithm for mock mode (3 nodes yield 4 interconnected links)
            const timestamp = Date.now();
            const newNodes = [
              { id: `node_${timestamp}_0`, group: Math.floor(Math.random() * 3) },
              { id: `node_${timestamp}_1`, group: Math.floor(Math.random() * 3) },
              { id: `node_${timestamp}_2`, group: Math.floor(Math.random() * 3) }
            ];
            
            setGraphData(prev => {
              if (prev.nodes.length === 0) {
                return { nodes: newNodes, links: [] };
              }
              const newLinks = [
                { source: (prev.nodes[Math.floor(Math.random() * prev.nodes.length)] as any)?.id || 'node_0', target: newNodes[0].id },
                { source: newNodes[0].id, target: newNodes[1].id },
                { source: newNodes[1].id, target: newNodes[2].id },
                { source: newNodes[2].id, target: (prev.nodes[Math.floor(Math.random() * prev.nodes.length)] as any)?.id || 'node_1' }
              ];
              return {
                nodes: [...prev.nodes, ...newNodes],
                links: [...prev.links, ...newLinks]
              };
            });
          }
        }

        setLogs(prev => [...prev, data]);
      } catch (e) {
        console.error('Error parsing SSE', e);
      }
    };

    return () => eventSource.close();
  }, [performAction]);

  // ── Node & Link interactive handlers ───────────────────────────────────
  const handleNodeClick = (node: any) => {
    setSelectedLinkId(null); // Clear link filter
    setSelectedNodeId(prev => prev === node.id ? null : node.id);
  };

  const handleLinkClick = (link: any) => {
    setSelectedNodeId(null); // Clear node filter
    const sourceId = link.source.id || link.source;
    const targetId = link.target.id || link.target;
    const linkId = `${sourceId}-${targetId}`;
    setSelectedLinkId(prev => prev === linkId ? null : linkId);
  };

  const nodeLabelHandler = (node: any) => {
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
    
    return `
      <div style="
        background: rgba(15, 23, 42, 0.95);
        color: #f8fafc;
        padding: 14px;
        border-radius: 12px;
        border: 1px solid #334155;
        font-family: 'Inter', sans-serif;
        font-size: 13px;
        max-width: 280px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.7);
        backdrop-filter: blur(4px);
        line-height: 1.5;
      ">
        <div style="font-weight: 800; font-size: 15px; color: #38bdf8; margin-bottom: 4px; display: flex; align-items: center; gap: 6px;">
          <span>${name}</span>
        </div>
        <div style="font-size: 10px; color: #94a3b8; font-weight: 700; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.05em;">
          ${role}
        </div>
        <div style="margin-bottom: 8px; font-size: 12px;">
          <strong style="color: #3b82f6;">👤 페르소나:</strong> 
          <span style="color: #cbd5e1;">${persona}</span>
        </div>
        <div style="font-size: 12px;">
          <strong style="color: #10b981;">🎯 검증 목표:</strong> 
          <span style="color: #cbd5e1;">${goal}</span>
        </div>
      </div>
    `;
  };

  const linkLabelHandler = (link: any) => {
    const sourceName = link.source.label || link.source.id || link.source;
    const targetName = link.target.label || link.target.id || link.target;
    return `
      <div style="
        background: rgba(15, 23, 42, 0.95);
        color: #cbd5e1;
        padding: 10px 14px;
        border-radius: 8px;
        border: 1px solid #334155;
        font-family: 'Inter', sans-serif;
        font-size: 12px;
        box-shadow: 0 8px 16px rgba(0,0,0,0.5);
        backdrop-filter: blur(4px);
      ">
        <div style="display: flex; align-items: center; gap: 8px;">
          <strong style="color: #38bdf8;">${sourceName}</strong>
          <span style="color: #64748b;">── 연계/의존 ──></span>
          <strong style="color: #f43f5e;">${targetName}</strong>
        </div>
      </div>
    `;
  };

  // ── Filtered Dialogue Feed ─────────────────────────────────────────────
  const filteredLogs = logs.filter(log => {
    if (selectedNodeId) {
      const selectedNode = graphData.nodes.find(n => n.id === selectedNodeId);
      if (!selectedNode) return true;
      if (log.type === 'agent_post') {
        const nodeName = selectedNode.label || selectedNode.id;
        const isAgentMatch = log.agent_name === nodeName || 
                             log.agent_name?.includes(nodeName) || 
                             nodeName.includes(log.agent_name || '');
                             
        const isMentioned = log.content?.toLowerCase().includes(nodeName.toLowerCase()) || 
                            log.content?.toLowerCase().includes(selectedNode.id.toLowerCase()) ||
                            (nodeName.length > 3 && log.content?.toLowerCase().includes(nodeName.substring(0, 4).toLowerCase()));
                            
        const connectedNodeIds = graphData.links
          .filter(l => {
            const sId = l.source.id || l.source;
            const tId = l.target.id || l.target;
            return sId === selectedNodeId || tId === selectedNodeId;
          })
          .map(l => {
            const sId = l.source.id || l.source;
            const tId = l.target.id || l.target;
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
      return false;
    }
    
    if (selectedLinkId) {
      const [sourceId, targetId] = selectedLinkId.split('-');
      const sourceNode = graphData.nodes.find(n => n.id === sourceId);
      const targetNode = graphData.nodes.find(n => n.id === targetId);
      if (!sourceNode || !targetNode) return true;
      if (log.type === 'agent_post') {
        const sourceName = sourceNode.label || sourceNode.id;
        const targetName = targetNode.label || targetNode.id;
        return log.agent_name === sourceName || log.agent_name === targetName ||
               log.agent_name?.includes(sourceName) || log.agent_name?.includes(targetName);
      }
      return false;
    }
    
    return true;
  });

  return (
    <div style={{ flex: 1, display: 'flex' }}>
      {/* Network Graph Area */}
      <div ref={containerRef} style={{ flex: 2, background: '#020617', position: 'relative' }}>
        <ForceGraph2D
          ref={fgRef}
          width={dimensions.width}
          height={dimensions.height}
          graphData={graphData}
          nodeAutoColorBy="group"
          linkColor={() => '#334155'}
          backgroundColor="#020617"
          nodeRelSize={6}
          d3AlphaDecay={0.05}
          d3VelocityDecay={0.2}
          nodeLabel={nodeLabelHandler}
          linkLabel={linkLabelHandler}
          onNodeClick={handleNodeClick}
          onLinkClick={handleLinkClick}
          onEngineStop={() => { console.log('Graph settled'); }}
        />
        
        {/* Graph Legend Panel */}
        <div style={{ 
          position: 'absolute', 
          bottom: 80, 
          left: 20, 
          background: 'rgba(15, 23, 42, 0.95)', 
          padding: '1rem', 
          borderRadius: '12px', 
          backdropFilter: 'blur(8px)', 
          border: '1px solid #334155',
          boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.5)',
          zIndex: 10,
          maxWidth: '280px',
          pointerEvents: 'auto'
        }}>
          <h4 style={{ margin: '0 0 10px 0', fontSize: '0.875rem', color: '#f8fafc', fontWeight: 700 }}>역할군(Group) 범례</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.75rem', color: '#cbd5e1' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ display: 'inline-block', width: '10px', height: '10px', borderRadius: '50%', background: '#3b82f6' }}></span>
              <span>기획 및 개발 (Group 0) - PM, 아키텍트 등</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ display: 'inline-block', width: '10px', height: '10px', borderRadius: '50%', background: '#10b981' }}></span>
              <span>보안 및 규제 (Group 1) - 감사관, 법무팀장</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ display: 'inline-block', width: '10px', height: '10px', borderRadius: '50%', background: '#eab308' }}></span>
              <span>재무, SRE, QA (Group 2) - CFO, QA, SRE</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ display: 'inline-block', width: '10px', height: '10px', borderRadius: '50%', background: '#a855f7' }}></span>
              <span>현업 및 생태계 (Group 3) - 영업, HR, 셀러</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ display: 'inline-block', width: '10px', height: '10px', borderRadius: '50%', background: '#ef4444' }}></span>
              <span>도출된 리스크 (Group 4) - 보안/재무/정산</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ display: 'inline-block', width: '10px', height: '10px', borderRadius: '50%', background: '#f97316' }}></span>
              <span>대안 및 솔루션 (Group 5) - HITL, 섀도우모드</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ display: 'inline-block', width: '10px', height: '10px', borderRadius: '50%', background: '#64748b' }}></span>
              <span>출시 마일스톤 (Group 6) - 런칭 목표</span>
            </div>
          </div>
        </div>

        <div style={{ position: 'absolute', top: 20, left: 20, background: 'rgba(15, 23, 42, 0.85)', padding: '1.25rem', borderRadius: '12px', backdropFilter: 'blur(6px)', border: '1px solid #334155', boxShadow: '0 10px 25px rgba(0,0,0,0.5)', zIndex: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            <h3 style={{ margin: 0, fontSize: '1rem', color: '#f8fafc', fontWeight: 800 }}>Simulation Network</h3>
            {simulationMode && (
              <span style={{ 
                display: 'inline-flex', 
                alignItems: 'center', 
                gap: '5px',
                fontSize: '0.7rem', 
                fontWeight: 700, 
                padding: '3px 8px', 
                borderRadius: '9999px',
                background: simulationMode === 'live' 
                  ? 'rgba(16, 185, 129, 0.15)' 
                  : simulationMode === 'live_fallback' 
                  ? 'rgba(239, 68, 68, 0.15)' 
                  : 'rgba(245, 158, 11, 0.15)',
                color: simulationMode === 'live' 
                  ? '#10b981' 
                  : simulationMode === 'live_fallback' 
                  ? '#ef4444' 
                  : '#f59e0b',
                border: simulationMode === 'live' 
                  ? '1px solid rgba(16, 185, 129, 0.3)' 
                  : simulationMode === 'live_fallback' 
                  ? '1px solid rgba(239, 68, 68, 0.3)' 
                  : '1px solid rgba(245, 158, 11, 0.3)',
                textTransform: 'uppercase',
                letterSpacing: '0.05em'
              }}>
                <span style={{ 
                  width: '6px', 
                  height: '6px', 
                  borderRadius: '50%', 
                  background: simulationMode === 'live' 
                    ? '#10b981' 
                    : simulationMode === 'live_fallback' 
                    ? '#ef4444' 
                    : '#f59e0b'
                }} />
                {simulationMode === 'live' 
                  ? 'MiroFish Live' 
                  : simulationMode === 'live_fallback' 
                  ? 'Live Failed (Fallback)' 
                  : 'Mock Mode'}
              </span>
            )}
          </div>
          <p style={{ margin: 0, color: '#94a3b8', fontSize: '0.875rem' }}>Nodes: {graphData.nodes.length} | Links: {graphData.links.length}</p>
        </div>

        <div style={{ position: 'absolute', bottom: 20, left: 20, right: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', pointerEvents: 'none' }}>
            <div style={{ flex: 1, marginRight: '2rem', pointerEvents: 'auto' }}>
                <div style={{ height: '4px', background: '#1e293b', borderRadius: '2px', overflow: 'hidden' }}>
                    <div style={{ width: `${progress}%`, height: '100%', background: '#3b82f6', transition: 'width 0.3s ease' }}></div>
                </div>
                <div style={{ textAlign: 'left', fontSize: '0.75rem', color: '#94a3b8', marginTop: '4px' }}>
                    {progress >= 100 ? '✅ Simulation Complete' : `Running... ${Math.round(progress)}%`}
                </div>
            </div>

            {progress >= 100 && (
              <button 
                onClick={() => performAction('stop_simulation')}
                style={{ 
                  pointerEvents: 'auto',
                  padding: '0.75rem 1.5rem', 
                  background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)', 
                  color: 'white', 
                  border: 'none', 
                  borderRadius: '12px', 
                  fontSize: '0.95rem', 
                  fontWeight: 600, 
                  cursor: 'pointer',
                  boxShadow: '0 10px 15px -3px rgba(37, 99, 235, 0.4)',
                  transition: 'all 0.2s ease',
                  whiteSpace: 'nowrap'
                }}
                onMouseOver={(e) => (e.currentTarget.style.transform = 'translateY(-2px)')}
                onMouseOut={(e) => (e.currentTarget.style.transform = 'translateY(0)')}
              >
                View Full Report →
              </button>
            )}
        </div>
      </div>

      {/* Real-time Feeds Array */}
      <div style={{ flex: 1, borderLeft: '1px solid #1e293b', background: '#0f172a', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '1rem', borderBottom: '1px solid #1e293b', background: '#020617', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ margin: 0, fontSize: '1rem', color: '#f8fafc' }}>Live Feed</h3>
            {(selectedNodeId || selectedLinkId) && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ 
                  background: '#1e293b', 
                  color: '#38bdf8', 
                  fontSize: '0.75rem', 
                  padding: '4px 8px', 
                  borderRadius: '6px', 
                  border: '1px solid #334155',
                  fontWeight: 600
                }}>
                  {selectedNodeId ? `필터: ${METADATA_DICTIONARY[selectedNodeId]?.role || selectedNodeId}` : '필터: 연결선'}
                </span>
                <button 
                  onClick={() => { setSelectedNodeId(null); setSelectedLinkId(null); }}
                  style={{
                    background: '#ef4444',
                    color: 'white',
                    border: 'none',
                    borderRadius: '6px',
                    padding: '4px 8px',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    transition: 'all 0.2s'
                  }}
                  onMouseOver={(e) => (e.currentTarget.style.background = '#dc2626')}
                  onMouseOut={(e) => (e.currentTarget.style.background = '#ef4444')}
                >
                  전체 보기
                </button>
              </div>
            )}
        </div>
        <div style={{ flex: 1, overflowY: 'auto', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {filteredLogs.length === 0 ? (
            <div style={{ color: '#64748b', fontSize: '0.875rem', textAlign: 'center', marginTop: '2rem' }}>
              해당 주체의 발언 내역이 없습니다.
            </div>
          ) : (
            filteredLogs.map((log, i) => (
              <div key={i} style={{ 
                  background: log.type === 'agent_post' ? '#1e293b' : 'transparent', 
                  padding: '0.75rem', 
                  borderRadius: '8px',
                  border: log.type === 'agent_post' ? '1px solid #334155' : 'none',
                  color: log.type === 'agent_post' ? '#e2e8f0' : '#64748b',
                  fontSize: '0.875rem'
              }}>
                  {log.type === 'agent_post' && (
                      <div style={{ fontWeight: 600, marginBottom: '0.25rem', color: '#38bdf8' }}>
                          {log.agent_name} <span style={{ color: '#64748b', fontWeight: 400, fontSize: '0.75rem' }}>({log.agent_type})</span>
                      </div>
                  )}
                  <div>{log.content || log.message}</div>
                  {log.timestamp && <div style={{ fontSize: '0.7rem', color: '#475569', marginTop: '0.5rem' }}>{new Date(log.timestamp).toLocaleTimeString()}</div>}
              </div>
            ))
          )}
          <div ref={logsEndRef} />
        </div>
      </div>
    </div>
  );
}
