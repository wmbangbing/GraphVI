// ============================================================
// 电影娱乐知识图谱 — 真实数据
// 运行: cypher-shell -u neo4j -p adminpassword -f seed-data.cql
// ============================================================

MATCH (n) DETACH DELETE n;

// ─── Studio ───────────────────────────────────────────────
CREATE (s1:Studio {id:'s1',name:'华特迪士尼影业',country:'美国',founded:1923})
CREATE (s2:Studio {id:'s2',name:'华纳兄弟影业',country:'美国',founded:1923})
CREATE (s3:Studio {id:'s3',name:'环球影业',country:'美国',founded:1912})
CREATE (s4:Studio {id:'s4',name:'派拉蒙影业',country:'美国',founded:1912})
CREATE (s5:Studio {id:'s5',name:'索尼哥伦比亚',country:'美国',founded:1924})
CREATE (s6:Studio {id:'s6',name:'中国电影集团',country:'中国',founded:1999});

// ─── Franchise ─────────────────────────────────────────────
MATCH (s1:Studio {id:'s1'}), (s2:Studio {id:'s2'}), (s3:Studio {id:'s3'}),
      (s4:Studio {id:'s4'}), (s5:Studio {id:'s5'}), (s6:Studio {id:'s6'})
CREATE (f1:Franchise {id:'f1',name:'漫威电影宇宙',genre:'超级英雄'})-[:OWNED_BY]->(s1)
CREATE (f2:Franchise {id:'f2',name:'哈利波特系列',genre:'奇幻'})-[:OWNED_BY]->(s2)
CREATE (f3:Franchise {id:'f3',name:'速度与激情',genre:'动作'})-[:OWNED_BY]->(s3)
CREATE (f4:Franchise {id:'f4',name:'侏罗纪世界',genre:'科幻'})-[:OWNED_BY]->(s3)
CREATE (f5:Franchise {id:'f5',name:'碟中谍',genre:'动作'})-[:OWNED_BY]->(s4)
CREATE (f6:Franchise {id:'f6',name:'星际大战',genre:'科幻'})-[:OWNED_BY]->(s1)
CREATE (f7:Franchise {id:'f7',name:'DC扩展宇宙',genre:'超级英雄'})-[:OWNED_BY]->(s2)
CREATE (f8:Franchise {id:'f8',name:'流浪地球',genre:'科幻'})-[:OWNED_BY]->(s6);

// ─── Movies ───────────────────────────────────────────────
MATCH (f1:Franchise {id:'f1'})
MATCH (f2:Franchise {id:'f2'})
MATCH (f3:Franchise {id:'f3'})
MATCH (f4:Franchise {id:'f4'})
MATCH (f5:Franchise {id:'f5'})
MATCH (f6:Franchise {id:'f6'})
MATCH (f7:Franchise {id:'f7'})
MATCH (f8:Franchise {id:'f8'})
WITH f1, f2, f3, f4, f5, f6, f7, f8

CREATE (m1:Movie {id:'m1',title:'钢铁侠',year:2008,rating:7.9,box_office:'5.85亿'})-[:BELONGS_TO]->(f1)
CREATE (m2:Movie {id:'m2',title:'复仇者联盟4：终局之战',year:2019,rating:8.5,box_office:'27.9亿'})-[:BELONGS_TO]->(f1)
CREATE (m3:Movie {id:'m3',title:'黑豹',year:2018,rating:7.3,box_office:'13.4亿'})-[:BELONGS_TO]->(f1)
CREATE (m4:Movie {id:'m4',title:'雷神3：诸神黄昏',year:2017,rating:7.7,box_office:'8.5亿'})-[:BELONGS_TO]->(f1)
CREATE (m5:Movie {id:'m5',title:'蜘蛛侠：英雄无归',year:2021,rating:8.3,box_office:'19.2亿'})-[:BELONGS_TO]->(f1)
CREATE (m6:Movie {id:'m6',title:'美国队长3：内战',year:2016,rating:7.8,box_office:'11.5亿'})-[:BELONGS_TO]->(f1)
CREATE (m7:Movie {id:'m7',title:'惊奇队长',year:2019,rating:6.8,box_office:'11.3亿'})-[:BELONGS_TO]->(f1)
CREATE (m8:Movie {id:'m8',title:'银河护卫队',year:2014,rating:8.0,box_office:'7.7亿'})-[:BELONGS_TO]->(f1)

CREATE (m9:Movie {id:'m9',title:'哈利波特与魔法石',year:2001,rating:8.1,box_office:'9.7亿'})-[:BELONGS_TO]->(f2)
CREATE (m10:Movie {id:'m10',title:'哈利波特与死亡圣器(下)',year:2011,rating:8.2,box_office:'13.4亿'})-[:BELONGS_TO]->(f2)
CREATE (m11:Movie {id:'m11',title:'神奇动物在哪里',year:2016,rating:7.5,box_office:'8.1亿'})-[:BELONGS_TO]->(f2)

CREATE (m12:Movie {id:'m12',title:'速度与激情7',year:2015,rating:8.2,box_office:'15.1亿'})-[:BELONGS_TO]->(f3)
CREATE (m13:Movie {id:'m13',title:'速度与激情8',year:2017,rating:7.1,box_office:'12.3亿'})-[:BELONGS_TO]->(f3)

CREATE (m14:Movie {id:'m14',title:'侏罗纪世界',year:2015,rating:7.0,box_office:'16.7亿'})-[:BELONGS_TO]->(f4)
CREATE (m15:Movie {id:'m15',title:'侏罗纪世界2',year:2018,rating:6.3,box_office:'13.0亿'})-[:BELONGS_TO]->(f4)

CREATE (m16:Movie {id:'m16',title:'碟中谍6：全面瓦解',year:2018,rating:8.1,box_office:'7.9亿'})-[:BELONGS_TO]->(f5)
CREATE (m17:Movie {id:'m17',title:'碟中谍7：致命清算(上)',year:2023,rating:7.8,box_office:'5.7亿'})-[:BELONGS_TO]->(f5)

CREATE (m18:Movie {id:'m18',title:'星球大战：原力觉醒',year:2015,rating:7.9,box_office:'20.6亿'})-[:BELONGS_TO]->(f6)
CREATE (m19:Movie {id:'m19',title:'星球大战：最后的绝地武士',year:2017,rating:7.0,box_office:'13.3亿'})-[:BELONGS_TO]->(f6)

CREATE (m20:Movie {id:'m20',title:'蝙蝠侠大战超人',year:2016,rating:6.5,box_office:'8.7亿'})-[:BELONGS_TO]->(f7)
CREATE (m21:Movie {id:'m21',title:'神奇女侠',year:2017,rating:7.4,box_office:'8.2亿'})-[:BELONGS_TO]->(f7)
CREATE (m22:Movie {id:'m22',title:'海王',year:2018,rating:7.6,box_office:'11.4亿'})-[:BELONGS_TO]->(f7)

CREATE (m23:Movie {id:'m23',title:'流浪地球',year:2019,rating:7.9,box_office:'6.9亿'})-[:BELONGS_TO]->(f8)
CREATE (m24:Movie {id:'m24',title:'流浪地球2',year:2023,rating:8.3,box_office:'5.9亿'})-[:BELONGS_TO]->(f8);

// ─── Characters ───────────────────────────────────────────
MATCH (m1:Movie {id:'m1'})
MATCH (m2:Movie {id:'m2'})
MATCH (m3:Movie {id:'m3'})
MATCH (m4:Movie {id:'m4'})
MATCH (m5:Movie {id:'m5'})
MATCH (m6:Movie {id:'m6'})
MATCH (m9:Movie {id:'m9'})
MATCH (m12:Movie {id:'m12'})
MATCH (m14:Movie {id:'m14'})
MATCH (m16:Movie {id:'m16'})
MATCH (m21:Movie {id:'m21'})
MATCH (m22:Movie {id:'m22'})
MATCH (m23:Movie {id:'m23'})
WITH m1, m2, m3, m4, m5, m6, m9, m12, m14, m16, m21, m22, m23

CREATE (c1:Character {id:'c1',name:'托尼·斯塔克',alias:'钢铁侠',gender:'男'})-[:APPEARS_IN]->(m1)
CREATE (c2:Character {id:'c2',name:'史蒂夫·罗杰斯',alias:'美国队长',gender:'男'})-[:APPEARS_IN]->(m6)
CREATE (c3:Character {id:'c3',name:'娜塔莎·罗曼诺夫',alias:'黑寡妇',gender:'女'})-[:APPEARS_IN]->(m2)
CREATE (c4:Character {id:'c4',name:'索尔',alias:'雷神',gender:'男'})-[:APPEARS_IN]->(m4)
CREATE (c5:Character {id:'c5',name:'特查拉',alias:'黑豹',gender:'男'})-[:APPEARS_IN]->(m3)
CREATE (c6:Character {id:'c6',name:'彼得·帕克',alias:'蜘蛛侠',gender:'男'})-[:APPEARS_IN]->(m5)
CREATE (c7:Character {id:'c7',name:'卡罗尔·丹弗斯',alias:'惊奇队长',gender:'女'})-[:APPEARS_IN]->(m7)
CREATE (c8:Character {id:'c8',name:'彼得·奎尔',alias:'星爵',gender:'男'})-[:APPEARS_IN]->(m8)
CREATE (c9:Character {id:'c9',name:'哈利·波特',alias:'救世主',gender:'男'})-[:APPEARS_IN]->(m9)
CREATE (c10:Character {id:'c10',name:'赫敏·格兰杰',alias:'万事通',gender:'女'})-[:APPEARS_IN]->(m9)
CREATE (c11:Character {id:'c11',name:'多米尼克·托雷托',alias:'唐老大',gender:'男'})-[:APPEARS_IN]->(m12)
CREATE (c12:Character {id:'c12',name:'欧文·格雷迪',alias:'恐龙训练师',gender:'男'})-[:APPEARS_IN]->(m14)
CREATE (c13:Character {id:'c13',name:'伊森·亨特',alias:'IMF特工',gender:'男'})-[:APPEARS_IN]->(m16)
CREATE (c14:Character {id:'c14',name:'戴安娜·普林斯',alias:'神奇女侠',gender:'女'})-[:APPEARS_IN]->(m21)
CREATE (c15:Character {id:'c15',name:'亚瑟·库瑞',alias:'海王',gender:'男'})-[:APPEARS_IN]->(m22)
CREATE (c16:Character {id:'c16',name:'刘培强',alias:'宇航员',gender:'男'})-[:APPEARS_IN]->(m23);

// Character connected to more movies
CREATE (c1)-[:APPEARS_IN]->(m2);
CREATE (c2)-[:APPEARS_IN]->(m2);
CREATE (c3)-[:APPEARS_IN]->(m1);
CREATE (c4)-[:APPEARS_IN]->(m2);

// ─── Actors ───────────────────────────────────────────────
MATCH (c1:Character {id:'c1'}), (c2:Character {id:'c2'}), (c3:Character {id:'c3'}),
      (c4:Character {id:'c4'}), (c5:Character {id:'c5'}), (c6:Character {id:'c6'}),
      (c7:Character {id:'c7'}), (c8:Character {id:'c8'}), (c9:Character {id:'c9'}),
      (c10:Character {id:'c10'}), (c11:Character {id:'c11'}), (c12:Character {id:'c12'}),
      (c13:Character {id:'c13'}), (c14:Character {id:'c14'}), (c15:Character {id:'c15'}),
      (c16:Character {id:'c16'})
CREATE (a1:Actor {id:'a1',name:'小罗伯特·唐尼',birth:1965,country:'美国',gender:'男'})-[:PORTRAYS]->(c1)
CREATE (a2:Actor {id:'a2',name:'克里斯·埃文斯',birth:1981,country:'美国',gender:'男'})-[:PORTRAYS]->(c2)
CREATE (a3:Actor {id:'a3',name:'斯嘉丽·约翰逊',birth:1984,country:'美国',gender:'女'})-[:PORTRAYS]->(c3)
CREATE (a4:Actor {id:'a4',name:'克里斯·海姆斯沃斯',birth:1983,country:'澳大利亚',gender:'男'})-[:PORTRAYS]->(c4)
CREATE (a5:Actor {id:'a5',name:'查德维克·博斯曼',birth:1977,country:'美国',gender:'男'})-[:PORTRAYS]->(c5)
CREATE (a6:Actor {id:'a6',name:'汤姆·霍兰德',birth:1996,country:'英国',gender:'男'})-[:PORTRAYS]->(c6)
CREATE (a7:Actor {id:'a7',name:'布丽·拉尔森',birth:1989,country:'美国',gender:'女'})-[:PORTRAYS]->(c7)
CREATE (a8:Actor {id:'a8',name:'克里斯·帕拉特',birth:1979,country:'美国',gender:'男'})-[:PORTRAYS]->(c8)
CREATE (a9:Actor {id:'a9',name:'丹尼尔·雷德克里夫',birth:1989,country:'英国',gender:'男'})-[:PORTRAYS]->(c9)
CREATE (a10:Actor {id:'a10',name:'艾玛·沃特森',birth:1990,country:'英国',gender:'女'})-[:PORTRAYS]->(c10)
CREATE (a11:Actor {id:'a11',name:'范·迪塞尔',birth:1967,country:'美国',gender:'男'})-[:PORTRAYS]->(c11)
CREATE (a12:Actor {id:'a12',name:'克里斯·帕拉特',birth:1979,country:'美国',gender:'男'})-[:PORTRAYS]->(c12)
CREATE (a13:Actor {id:'a13',name:'汤姆·克鲁斯',birth:1962,country:'美国',gender:'男'})-[:PORTRAYS]->(c13)
CREATE (a14:Actor {id:'a14',name:'盖尔·加朵',birth:1985,country:'以色列',gender:'女'})-[:PORTRAYS]->(c14)
CREATE (a15:Actor {id:'a15',name:'杰森·莫玛',birth:1979,country:'美国',gender:'男'})-[:PORTRAYS]->(c15)
CREATE (a16:Actor {id:'a16',name:'吴京',birth:1974,country:'中国',gender:'男'})-[:PORTRAYS]->(c16);

// Cross-movie actors
MATCH (a1:Actor {id:'a1'}), (m3:Movie {id:'m3'})
CREATE (c17:Character {id:'c17',name:'托尼·斯塔克',alias:'钢铁侠',gender:'男'})
MERGE (c17)-[:APPEARS_IN]->(m3)
MERGE (a1)-[:PORTRAYS]->(c17);

// ─── Agents ───────────────────────────────────────────────
MATCH (a1:Actor {id:'a1'}), (a2:Actor {id:'a2'}), (a3:Actor {id:'a3'}), (a5:Actor {id:'a5'}),
      (a9:Actor {id:'a9'}), (a11:Actor {id:'a11'}), (a13:Actor {id:'a13'}), (a14:Actor {id:'a14'}),
      (a16:Actor {id:'a16'})
CREATE (ag1:Agent {id:'ag1',name:'创新艺人经纪公司',company:'CAA',location:'洛杉矶'})
CREATE (ag2:Agent {id:'ag2',name:'威廉·莫里斯奋进',company:'WME',location:'纽约'})
CREATE (ag3:Agent {id:'ag3',name:'联合人才经纪公司',company:'UTA',location:'洛杉矶'})
CREATE (ag4:Agent {id:'ag4',name:'北京文化经纪',company:'京艺',location:'北京'})
CREATE (ag1)-[:REPRESENTS]->(a1)
CREATE (ag1)-[:REPRESENTS]->(a3)
CREATE (ag2)-[:REPRESENTS]->(a2)
CREATE (ag2)-[:REPRESENTS]->(a13)
CREATE (ag3)-[:REPRESENTS]->(a5)
CREATE (ag3)-[:REPRESENTS]->(a9)
CREATE (ag3)-[:REPRESENTS]->(a11)
CREATE (ag1)-[:REPRESENTS]->(a14)
CREATE (ag4)-[:REPRESENTS]->(a16);

// ─── Awards ───────────────────────────────────────────────
MATCH (a1:Actor {id:'a1'}), (a3:Actor {id:'a3'}), (a7:Actor {id:'a7'}),
      (a13:Actor {id:'a13'}), (a16:Actor {id:'a16'}),
      (m2:Movie {id:'m2'}), (m12:Movie {id:'m12'}), (m23:Movie {id:'m23'})
CREATE (aw1:Award {id:'aw1',name:'奥斯卡最佳男主角',year:2020,ceremony:'第92届奥斯卡'})
CREATE (aw2:Award {id:'aw2',name:'金球奖最佳女主角',year:2020,ceremony:'第77届金球奖'})
CREATE (aw3:Award {id:'aw3',name:'奥斯卡最佳女主角',year:2016,ceremony:'第88届奥斯卡'})
CREATE (aw4:Award {id:'aw4',name:'金球奖剧情类最佳男主角',year:2019,ceremony:'第76届金球奖'})
CREATE (aw5:Award {id:'aw5',name:'华表奖优秀电影',year:2021,ceremony:'第18届华表奖'})
CREATE (aw6:Award {id:'aw6',name:'奥斯卡最佳视觉效果',year:2020,ceremony:'第92届奥斯卡'})
CREATE (aw7:Award {id:'aw7',name:'MTV电影奖最佳动作场面',year:2016,ceremony:'MTV电影奖'})
CREATE (aw8:Award {id:'aw8',name:'金鸡奖最佳故事片',year:2023,ceremony:'第36届金鸡奖'})
CREATE (a1)-[:WON]->(aw1)
CREATE (a3)-[:WON]->(aw2)
CREATE (a7)-[:WON]->(aw3)
CREATE (a13)-[:WON]->(aw4)
CREATE (m2)-[:WON]->(aw6)
CREATE (m12)-[:WON]->(aw7)
CREATE (m23)-[:WON]->(aw8)
CREATE (a16)-[:WON]->(aw5);

// ─── REPORTS_TO (simulating actor seniority chain) ────────
MATCH (a13:Actor {id:'a13'}), (a11:Actor {id:'a11'}), (a1:Actor {id:'a1'}),
      (a2:Actor {id:'a2'}), (a4:Actor {id:'a4'}), (a6:Actor {id:'a6'}),
      (a9:Actor {id:'a9'}), (a16:Actor {id:'a16'})
CREATE (a6)-[:REPORTS_TO]->(a2)
CREATE (a2)-[:REPORTS_TO]->(a1)
CREATE (a9)-[:REPORTS_TO]->(a11)
CREATE (a4)-[:REPORTS_TO]->(a13)
CREATE (a16)-[:REPORTS_TO]->(a1);

// ─── 扩展数据：批量生成补充角色和演员 ──────────────────────
MATCH (m:Movie)
WITH m
UNWIND range(1, 30) AS idx
CREATE (c:Character {id: m.id + '_ec' + idx, name: m.title + '群演' + idx, role_type: '配角', gender: ['男','女'][toInteger(rand()*2)]})
MERGE (c)-[:APPEARS_IN]->(m)
WITH c, m
CREATE (a:Actor {id: c.id + '_ea', name: ['赵薇','黄渤','徐峥','王宝强','刘亦菲','邓超','周迅','陈坤','杨幂','李现','迪丽热巴','肖战','易烊千玺','张译','雷佳音','刘昊然','王俊凯','关晓彤','周冬雨','马思纯','张家辉','梁朝伟','金城武','林志玲','张震','彭于晏','阮经天','赵又廷','杨紫','白敬亭'][toInteger(rand()*30)], birth: toInteger(1960 + rand()*40), country: ['中国','中国','中国','中国','美国','英国','韩国'][toInteger(rand()*7)], gender: ['男','女'][toInteger(rand()*2)]})
MERGE (a)-[:PORTRAYS]->(c);

// ─── 批量 Awards ─────────────────────────────────────────
MATCH (a:Actor) WITH a
UNWIND range(1, toInteger(1 + rand()*1)) AS idx
CREATE (aw:Award {id: a.id + '_eaw' + idx, name: ['奥斯卡最佳男主角','奥斯卡最佳导演','金球奖','金鸡奖','金马奖','艾美奖','戛纳金棕榈','金狮奖','柏林金熊奖','华表奖','金鹰奖','百花奖'][toInteger(rand()*12)], year: 2010 + toInteger(rand()*14)})
MERGE (a)-[:WON]->(aw);

// ─── 批量 Agents ─────────────────────────────────────────
MATCH (a:Actor) WITH a SKIP 20
WITH a, toInteger(rand()*50) AS agent_id
MERGE (ag:Agent {id: 'agent_' + agent_id})
ON CREATE SET ag.name = ['CAA','WME','UTA','ICM','北京文化','英皇娱乐','天娱传媒','嘉行传媒'][agent_id % 8], ag.country = ['美国','美国','美国','中国','中国'][agent_id % 5]
MERGE (ag)-[:REPRESENTS]->(a);

// ─── REPORTS_TO 多层汇报链 ────────────────────────────────
MATCH (a:Actor) WITH collect(a) AS actors
UNWIND range(1, size(actors)-1) AS idx
WITH actors[idx] AS a, actors[toInteger(idx/2)] AS mgr
WHERE a <> mgr AND a.birth < mgr.birth
MERGE (a)-[:REPORTS_TO]->(mgr);

// ─── 统计 ───────────────────────────────────────────────
MATCH (n) WITH count(n) AS nodeCount
MATCH ()-[r]->() WITH nodeCount, count(r) AS relCount
RETURN nodeCount AS 节点数, relCount AS 关系数;
