from dataclasses import dataclass


@dataclass
class JobPosting:
    id: str          # "사이트:공고ID", 예: "wanted:12345"
    site: str        # wanted | saramin | rocketpunch
    title: str
    company: str
    location: str
    experience: str  # 사이트 원문 그대로
    url: str
    description: str  # 상세 본문, 없으면 ""
    posted_at: str    # 모집 시작일(ISO 날짜), 없으면 ""
    deadline: str = ""  # 모집 마감일(ISO 날짜), 없으면 ""
    company_size: str = ""  # 기업규모(대기업/중견기업/공기업 등), 제공 사이트만 채움
