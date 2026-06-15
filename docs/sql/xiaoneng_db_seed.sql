-- ============================================================
-- EfficiencyAgent 研发效能库 xiaoneng_db
-- 建表 + 假数据（逻辑自洽，可直接导入 MySQL）
-- 用法: mysql -u root -p < docs/sql/xiaoneng_db_seed.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS xiaoneng_db
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE xiaoneng_db;

-- 清理旧表（按外键依赖倒序）
DROP TABLE IF EXISTS work_logs;
DROP TABLE IF EXISTS defects;
DROP TABLE IF EXISTS requirements;
DROP TABLE IF EXISTS iterations;
DROP TABLE IF EXISTS team_members;

-- ------------------------------------------------------------
-- 1. 团队成员
-- ------------------------------------------------------------
CREATE TABLE team_members (
  member_id     INT PRIMARY KEY AUTO_INCREMENT,
  name          VARCHAR(50)  NOT NULL,
  role          VARCHAR(30)  NOT NULL COMMENT 'dev/test/pm/tl',
  email         VARCHAR(100) NOT NULL,
  is_active     TINYINT(1)   NOT NULL DEFAULT 1,
  joined_at     DATE         NOT NULL
) COMMENT='研发团队成员';

-- ------------------------------------------------------------
-- 2. 迭代
-- ------------------------------------------------------------
CREATE TABLE iterations (
  iteration_id    INT PRIMARY KEY AUTO_INCREMENT,
  iteration_code  VARCHAR(30)  NOT NULL UNIQUE COMMENT '如 2026-Sprint-12',
  iteration_name  VARCHAR(100) NOT NULL,
  start_date      DATE         NOT NULL,
  end_date        DATE         NOT NULL,
  planned_points  INT          NOT NULL DEFAULT 0 COMMENT '计划故事点',
  completed_points INT         NOT NULL DEFAULT 0 COMMENT '完成故事点',
  status          VARCHAR(20)  NOT NULL COMMENT 'planning/active/completed',
  team_goal       VARCHAR(255) DEFAULT NULL
) COMMENT='敏捷迭代';

-- ------------------------------------------------------------
-- 3. 需求
-- ------------------------------------------------------------
CREATE TABLE requirements (
  requirement_id   INT PRIMARY KEY AUTO_INCREMENT,
  req_code         VARCHAR(30)  NOT NULL UNIQUE COMMENT '如 REQ-2026-0042',
  title            VARCHAR(200) NOT NULL,
  iteration_id     INT          NOT NULL,
  assignee_id      INT          DEFAULT NULL,
  priority         VARCHAR(10)  NOT NULL COMMENT 'P0/P1/P2',
  story_points     INT          NOT NULL DEFAULT 0,
  status           VARCHAR(20)  NOT NULL COMMENT 'todo/in_progress/done/cancelled',
  req_type         VARCHAR(20)  NOT NULL COMMENT 'feature/bugfix/tech_debt',
  created_at       DATETIME     NOT NULL,
  started_at       DATETIME     DEFAULT NULL,
  completed_at     DATETIME     DEFAULT NULL,
  FOREIGN KEY (iteration_id) REFERENCES iterations(iteration_id),
  FOREIGN KEY (assignee_id)   REFERENCES team_members(member_id)
) COMMENT='产品需求/用户故事';

-- ------------------------------------------------------------
-- 4. 缺陷
-- ------------------------------------------------------------
CREATE TABLE defects (
  defect_id        INT PRIMARY KEY AUTO_INCREMENT,
  defect_code      VARCHAR(30)  NOT NULL UNIQUE COMMENT '如 BUG-2026-0188',
  title            VARCHAR(200) NOT NULL,
  requirement_id   INT          DEFAULT NULL COMMENT '关联需求，可为空',
  iteration_id     INT          NOT NULL COMMENT '发现所在迭代',
  reporter_id      INT          NOT NULL,
  assignee_id      INT          DEFAULT NULL,
  severity         VARCHAR(20)  NOT NULL COMMENT 'critical/major/minor/trivial',
  status           VARCHAR(20)  NOT NULL COMMENT 'open/fixed/verified/closed/reopened',
  env              VARCHAR(20)  NOT NULL DEFAULT 'test' COMMENT 'test/staging/prod',
  created_at       DATETIME     NOT NULL,
  fixed_at         DATETIME     DEFAULT NULL,
  verified_at      DATETIME     DEFAULT NULL,
  FOREIGN KEY (requirement_id) REFERENCES requirements(requirement_id),
  FOREIGN KEY (iteration_id)   REFERENCES iterations(iteration_id),
  FOREIGN KEY (reporter_id)    REFERENCES team_members(member_id),
  FOREIGN KEY (assignee_id)     REFERENCES team_members(member_id)
) COMMENT='缺陷/Bug';

-- ------------------------------------------------------------
-- 5. 工时记录
-- ------------------------------------------------------------
CREATE TABLE work_logs (
  log_id           INT PRIMARY KEY AUTO_INCREMENT,
  member_id        INT          NOT NULL,
  requirement_id   INT          DEFAULT NULL,
  defect_id        INT          DEFAULT NULL,
  iteration_id     INT          NOT NULL,
  work_date        DATE         NOT NULL,
  hours            DECIMAL(4,1) NOT NULL,
  task_type        VARCHAR(20)  NOT NULL COMMENT 'dev/test/review/meeting/doc',
  note             VARCHAR(255) DEFAULT NULL,
  FOREIGN KEY (member_id)      REFERENCES team_members(member_id),
  FOREIGN KEY (requirement_id) REFERENCES requirements(requirement_id),
  FOREIGN KEY (defect_id)      REFERENCES defects(defect_id),
  FOREIGN KEY (iteration_id)   REFERENCES iterations(iteration_id)
) COMMENT='成员工时';

-- ============================================================
-- 假数据
-- ============================================================

INSERT INTO team_members (name, role, email, joined_at) VALUES
('张明',   'tl',   'zhangming@company.com',  '2024-03-01'),
('李薇',   'pm',   'liwei@company.com',        '2024-06-15'),
('王浩',   'dev',  'wanghao@company.com',      '2024-08-01'),
('陈悦',   'dev',  'chenyue@company.com',      '2025-01-10'),
('赵磊',   'dev',  'zhaolei@company.com',      '2025-04-20'),
('刘婷',   'test', 'liuting@company.com',      '2024-09-01'),
('孙凯',   'test', 'sunkai@company.com',       '2025-02-18');

-- 迭代（Sprint-08 ~ Sprint-12，当前日期 2026-06-04 在 Sprint-12）
INSERT INTO iterations (iteration_code, iteration_name, start_date, end_date, planned_points, completed_points, status, team_goal) VALUES
('2026-Sprint-08', '四月迭代：效能看板 MVP',     '2026-04-07', '2026-04-18', 34, 30, 'completed', '上线效能数据采集看板'),
('2026-Sprint-09', '四月迭代：报表导出',         '2026-04-21', '2026-05-02', 28, 26, 'completed', '支持周报 Excel 导出'),
('2026-Sprint-10', '五月迭代：Agent 原型',       '2026-05-05', '2026-05-16', 32, 28, 'completed', '完成 Multi-Agent 查数 POC'),
('2026-Sprint-11', '五月迭代：SQL 安全与鉴权',   '2026-05-19', '2026-05-30', 26, 24, 'completed', 'DB 只读 + API Key 鉴权'),
('2026-Sprint-12', '六月迭代：效能 Agent 集成',  '2026-06-02', '2026-06-13', 30, 12, 'active',    '打通查数-分析-写报告全链路');

-- 需求（跨 Sprint-10 ~ Sprint-12）
INSERT INTO requirements (req_code, title, iteration_id, assignee_id, priority, story_points, status, req_type, created_at, started_at, completed_at) VALUES
-- Sprint-10（均已 done）
('REQ-2026-0031', '效能指标字典表设计',           3, 3, 'P0', 5, 'done', 'feature',    '2026-05-05 09:00:00', '2026-05-05 10:00:00', '2026-05-07 18:00:00'),
('REQ-2026-0032', 'DeepAgents 主 Agent 骨架',     3, 4, 'P0', 8, 'done', 'feature',    '2026-05-05 09:30:00', '2026-05-06 09:00:00', '2026-05-12 17:30:00'),
('REQ-2026-0033', '数据库只读 Tool 封装',         3, 5, 'P0', 5, 'done', 'feature',    '2026-05-06 14:00:00', '2026-05-07 09:00:00', '2026-05-10 16:00:00'),
('REQ-2026-0034', 'WebSocket 进度推送 POC',       3, 3, 'P1', 5, 'done', 'feature',    '2026-05-08 11:00:00', '2026-05-09 09:00:00', '2026-05-14 15:00:00'),
('REQ-2026-0035', '迭代复盘报告模板',             3, 4, 'P2', 3, 'done', 'feature',    '2026-05-10 10:00:00', '2026-05-12 09:00:00', '2026-05-15 12:00:00'),
('REQ-2026-0036', 'Tavily 行业检索接入',          3, 5, 'P1', 3, 'cancelled', 'feature', '2026-05-11 09:00:00', NULL, NULL),

-- Sprint-11（均已 done）
('REQ-2026-0041', 'SQL 注入防护与白名单',         4, 5, 'P0', 5, 'done', 'tech_debt',  '2026-05-19 09:00:00', '2026-05-19 10:00:00', '2026-05-21 17:00:00'),
('REQ-2026-0042', 'API Key 鉴权中间件',           4, 3, 'P0', 5, 'done', 'feature',    '2026-05-19 09:30:00', '2026-05-20 09:00:00', '2026-05-23 16:30:00'),
('REQ-2026-0043', '任务状态机 REST 接口',         4, 4, 'P0', 8, 'done', 'feature',    '2026-05-20 14:00:00', '2026-05-21 09:00:00', '2026-05-27 18:00:00'),
('REQ-2026-0044', '上传文件类型与大小校验',       4, 5, 'P1', 3, 'done', 'feature',    '2026-05-22 10:00:00', '2026-05-23 09:00:00', '2026-05-26 14:00:00'),
('REQ-2026-0045', '结构化 JSON 日志',             4, 3, 'P1', 3, 'done', 'tech_debt',  '2026-05-24 09:00:00', '2026-05-25 09:00:00', '2026-05-28 11:00:00'),

-- Sprint-12（当前迭代，混合状态）
('REQ-2026-0051', '5 个子 Agent Prompt 效能域改写', 5, 4, 'P0', 5, 'done', 'feature',    '2026-06-02 09:00:00', '2026-06-02 10:00:00', '2026-06-03 17:00:00'),
('REQ-2026-0052', '指标分析子 Agent 接入',          5, 3, 'P0', 8, 'in_progress', 'feature', '2026-06-02 09:30:00', '2026-06-03 09:00:00', NULL),
('REQ-2026-0053', '报告撰写子 Agent 接入',          5, 5, 'P0', 5, 'in_progress', 'feature', '2026-06-02 10:00:00', '2026-06-04 09:00:00', NULL),
('REQ-2026-0054', 'xiaoneng_db 效能假数据脚本',     5, 4, 'P1', 2, 'done', 'feature',    '2026-06-03 14:00:00', '2026-06-04 09:00:00', '2026-06-04 11:00:00'),
('REQ-2026-0055', '端到端：上传测试报告写复盘',     5, 3, 'P0', 5, 'todo', 'feature',    '2026-06-04 10:00:00', NULL, NULL),
('REQ-2026-0056', 'RAGFlow 规范知识助手接入',       5, 5, 'P1', 5, 'todo', 'feature',    '2026-06-04 11:00:00', NULL, NULL);

-- 缺陷
INSERT INTO defects (defect_code, title, requirement_id, iteration_id, reporter_id, assignee_id, severity, status, env, created_at, fixed_at, verified_at) VALUES
-- Sprint-10 缺陷（已关闭）
('BUG-2026-0101', 'SQL 查询超时未返回友好错误',     3, 3, 6, 5, 'major',   'closed',   'test', '2026-05-08 15:30:00', '2026-05-09 11:00:00', '2026-05-09 16:00:00'),
('BUG-2026-0102', 'WebSocket 断连后进度丢失',       4, 3, 7, 3, 'major',   'closed',   'test', '2026-05-13 10:00:00', '2026-05-14 14:00:00', '2026-05-14 17:00:00'),
('BUG-2026-0103', '需求列表分页参数校验缺失',       2, 3, 6, 4, 'minor',   'closed',   'test', '2026-05-11 09:20:00', '2026-05-11 17:00:00', '2026-05-12 10:00:00'),

-- Sprint-11 缺陷
('BUG-2026-0110', 'API Key 为空时返回 500 而非 401', 8, 4, 7, 3, 'major',   'closed',   'test', '2026-05-22 16:00:00', '2026-05-23 10:30:00', '2026-05-23 15:00:00'),
('BUG-2026-0111', '任务状态 pending 未自动转 running', 9, 4, 6, 4, 'major',   'closed',   'test', '2026-05-25 11:00:00', '2026-05-26 09:00:00', '2026-05-26 14:00:00'),
('BUG-2026-0112', '上传 21MB 文件未拦截',           10, 4, 7, 5, 'critical','closed',   'test', '2026-05-27 09:00:00', '2026-05-27 15:00:00', '2026-05-28 10:00:00'),

-- Sprint-12 当前缺陷（含 open / fixed）
('BUG-2026-0120', '指标分析 Agent 偶发空响应',      13, 5, 6, 3, 'major',   'fixed',    'test', '2026-06-03 16:00:00', '2026-06-04 10:30:00', NULL),
('BUG-2026-0121', '报告文件名中文乱码',             14, 5, 7, 5, 'minor',   'open',     'test', '2026-06-04 09:15:00', NULL, NULL),
('BUG-2026-0122', '并发两任务 session 目录冲突',    12, 5, 6, 3, 'critical','open',     'test', '2026-06-04 11:30:00', NULL, NULL),
('BUG-2026-0123', '生产环境日志 trace_id 缺失',     11, 5, 7, 3, 'major',   'open',     'prod', '2026-06-04 08:00:00', NULL, NULL);

-- 工时（Sprint-12 本周部分记录，2026-06-02 ~ 2026-06-04）
INSERT INTO work_logs (member_id, requirement_id, defect_id, iteration_id, work_date, hours, task_type, note) VALUES
(3, 12, NULL, 5, '2026-06-02', 6.0, 'dev',     'Prompt 效能域改写'),
(4, 12, NULL, 5, '2026-06-02', 5.5, 'dev',     'prompts.yml 五子 Agent'),
(5, 13, NULL, 5, '2026-06-02', 4.0, 'dev',     '报告 Agent 骨架'),
(6, NULL, NULL, 5, '2026-06-02', 3.0, 'test',  'Sprint-12 测试计划'),
(3, 13, NULL, 5, '2026-06-03', 7.0, 'dev',     '指标分析 Agent 联调'),
(4, 12, NULL, 5, '2026-06-03', 4.0, 'dev',     'loader 校验逻辑'),
(5, 14, NULL, 5, '2026-06-03', 6.0, 'dev',     'markdown 工具对接'),
(6, NULL, 9,  5, '2026-06-03', 2.5, 'test',    '验证 BUG-0120 复现'),
(7, NULL, 9,  5, '2026-06-03', 2.0, 'test',    '回归测试'),
(3, 13, 9,  5, '2026-06-04', 5.0, 'dev',     '修复指标分析空响应'),
(4, 15, NULL, 5, '2026-06-04', 3.0, 'dev',     '假数据 SQL 脚本'),
(5, 14, 10, 5, '2026-06-04', 4.5, 'dev',     '排查中文文件名乱码'),
(6, 15, NULL, 5, '2026-06-04', 4.0, 'test',  '端到端用例准备'),
(1, NULL, NULL, 5, '2026-06-04', 1.5, 'meeting','Sprint-12 站会');

-- ============================================================
-- 常用查询视图（Agent 查数时可参考）
-- ============================================================
CREATE OR REPLACE VIEW v_iteration_summary AS
SELECT
  i.iteration_code,
  i.iteration_name,
  i.start_date,
  i.end_date,
  i.status,
  i.planned_points,
  i.completed_points,
  ROUND(i.completed_points / NULLIF(i.planned_points, 0) * 100, 1) AS completion_rate_pct,
  COUNT(DISTINCT r.requirement_id) AS total_requirements,
  SUM(CASE WHEN r.status = 'done' THEN 1 ELSE 0 END) AS done_requirements,
  COUNT(DISTINCT d.defect_id) AS total_defects,
  SUM(CASE WHEN d.status IN ('open','reopened') THEN 1 ELSE 0 END) AS open_defects
FROM iterations i
LEFT JOIN requirements r ON r.iteration_id = i.iteration_id
LEFT JOIN defects d ON d.iteration_id = i.iteration_id
GROUP BY i.iteration_id;

CREATE OR REPLACE VIEW v_defect_fix_duration AS
SELECT
  d.defect_code,
  d.title,
  d.severity,
  d.status,
  i.iteration_code,
  TIMESTAMPDIFF(HOUR, d.created_at, d.fixed_at) AS fix_hours,
  r.req_code AS related_requirement
FROM defects d
JOIN iterations i ON d.iteration_id = i.iteration_id
LEFT JOIN requirements r ON d.requirement_id = r.requirement_id
WHERE d.fixed_at IS NOT NULL;
