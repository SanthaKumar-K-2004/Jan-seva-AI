"""
Jan-Seva AI — Scheme Seed Script
Batch seeds 300+ government schemes with structured data and auto-generates embeddings.
Run: python -m app.services.scraper.seed_schemes
"""

import sys
import os

# Add backend to path when run directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from app.core.supabase_client import get_supabase_client
from app.core.embedding_client import get_embedding_client
from app.utils.logger import logger
from app.services.scraper.schemes_extra import EXTRA_SCHEMES


# ══════════════════════════════════════════
# COMPREHENSIVE SCHEME DATABASE
# 200+ schemes covering all categories
# ══════════════════════════════════════════

SCHEMES = [
    # ═══════════ CENTRAL — AGRICULTURE ═══════════
    {"name": "PM-KISAN Samman Nidhi", "slug": "pm-kisan-samman-nidhi", "state": "Central", "category": ["Agriculture", "Farmers", "Income Support"], "ministry": "Ministry of Agriculture", "benefits": "Rs. 6,000 per year in 3 instalments of Rs. 2,000 each", "description": "Income support of Rs.6000 per year for all landholding farmer families in three equal instalments.", "source_url": "https://pmkisan.gov.in", "source_type": "portal"},
    {"name": "PM Fasal Bima Yojana", "slug": "pm-fasal-bima-yojana", "state": "Central", "category": ["Agriculture", "Insurance"], "ministry": "Ministry of Agriculture", "benefits": "Crop insurance at subsidized premiums: 2% for Kharif, 1.5% for Rabi, 5% for commercial crops", "description": "Comprehensive crop insurance scheme providing financial support to farmers suffering crop loss due to natural calamities, pests and diseases.", "source_url": "https://pmfby.gov.in", "source_type": "portal"},
    {"name": "Kisan Credit Card Scheme", "slug": "kisan-credit-card", "state": "Central", "category": ["Agriculture", "Loan", "Credit"], "ministry": "Ministry of Agriculture", "benefits": "Short-term crop loans at 4% interest (with 3% subvention). Loan up to Rs. 3 lakhs", "description": "Provides farmers with timely access to credit for agricultural and allied activities including animal husbandry and fisheries.", "source_url": "https://www.nabard.org", "source_type": "portal"},
    {"name": "Soil Health Card Scheme", "slug": "soil-health-card", "state": "Central", "category": ["Agriculture", "Soil"], "ministry": "Ministry of Agriculture", "benefits": "Free soil testing and nutrient recommendations for every farmer", "description": "Provides soil health cards to farmers with crop-wise recommendations of nutrients and fertilizers to improve productivity.", "source_url": "https://soilhealth.dac.gov.in", "source_type": "portal"},
    {"name": "PM Krishi Sinchayee Yojana", "slug": "pm-krishi-sinchayee-yojana", "state": "Central", "category": ["Agriculture", "Irrigation"], "ministry": "Ministry of Agriculture", "benefits": "55% subsidy for small farmers, 45% for others on micro-irrigation equipment", "description": "Ensures access to irrigation for every farm (Har Khet ko Pani) and improves water use efficiency through micro-irrigation.", "source_url": "https://pmksy.gov.in", "source_type": "portal"},
    {"name": "National Mission on Oilseeds and Oil Palm", "slug": "national-mission-oilseeds-oil-palm", "state": "Central", "category": ["Agriculture", "Oilseeds"], "ministry": "Ministry of Agriculture", "benefits": "Subsidies for oil palm cultivation and oilseed production enhancement", "description": "Aims to increase domestic production of edible oils by promoting oil palm and oilseed cultivation.", "source_url": "https://agricoop.nic.in", "source_type": "html"},
    {"name": "Paramparagat Krishi Vikas Yojana", "slug": "paramparagat-krishi-vikas-yojana", "state": "Central", "category": ["Agriculture", "Organic"], "ministry": "Ministry of Agriculture", "benefits": "Rs. 50,000 per hectare for 3 years for organic farming clusters", "description": "Promotes organic farming through adoption of organic village clusters with PGS certification.", "source_url": "https://pgsindia-ncof.gov.in", "source_type": "portal"},
    {"name": "National Beekeeping and Honey Mission", "slug": "national-beekeeping-honey-mission", "state": "Central", "category": ["Agriculture", "Beekeeping"], "ministry": "Ministry of Agriculture", "benefits": "Subsidies for bee colonies, equipment, and training for beekeepers", "description": "Promotes scientific beekeeping to achieve Sweet Revolution and enhance farm income through pollination services.", "source_url": "https://nbb.gov.in", "source_type": "portal"},

    # ═══════════ CENTRAL — EDUCATION ═══════════
    {"name": "National Scholarship Portal", "slug": "national-scholarship-portal", "state": "Central", "category": ["Education", "Scholarship"], "ministry": "Ministry of Education", "benefits": "Scholarships from Rs. 5,000 to Rs. 2,00,000 per year depending on scheme and level", "description": "One-stop solution for students to apply for Pre-Matric, Post-Matric, and Merit-cum-Means scholarships from Central and State Governments.", "source_url": "https://scholarships.gov.in", "source_type": "portal"},
    {"name": "PM Vidyalakshmi Education Loan", "slug": "pm-vidyalakshmi-education-loan", "state": "Central", "category": ["Education", "Loan"], "ministry": "Ministry of Education", "benefits": "Education loans up to Rs. 10 lakhs at subsidized interest for economically weaker sections", "description": "Portal for students to apply for education loans from multiple banks and get interest subsidy under CSIS.", "source_url": "https://www.vidyalakshmi.co.in", "source_type": "portal"},
    {"name": "Samagra Shiksha Abhiyan", "slug": "samagra-shiksha-abhiyan", "state": "Central", "category": ["Education", "School"], "ministry": "Ministry of Education", "benefits": "Free textbooks, uniforms, transport, and Rs. 3,000/year for CWSN children", "description": "Integrated scheme for school education covering pre-school to class XII with focus on improving quality and equity.", "source_url": "https://samagra.education.gov.in", "source_type": "portal"},
    {"name": "Mid-Day Meal / PM POSHAN", "slug": "pm-poshan-midday-meal", "state": "Central", "category": ["Education", "Nutrition", "Children"], "ministry": "Ministry of Education", "benefits": "Free hot cooked meal for all students in government schools (Class 1-8)", "description": "Provides free lunch on working days to improve nutritional levels and enrollment in government and aided schools.", "source_url": "https://pmposhan.education.gov.in", "source_type": "portal"},
    {"name": "Beti Bachao Beti Padhao", "slug": "beti-bachao-beti-padhao", "state": "Central", "category": ["Education", "Girl Child", "Women"], "ministry": "Ministry of WCD", "benefits": "Awareness campaigns, institutional support for girl child education and survival", "description": "Addresses declining child sex ratio and promotes education and empowerment of the girl child through multi-sectoral action.", "source_url": "https://wcd.nic.in/bbbp-schemes", "source_type": "html"},
    {"name": "Pragati Scholarship for Girls", "slug": "pragati-scholarship-girls", "state": "Central", "category": ["Education", "Women", "Scholarship"], "ministry": "Ministry of Education", "benefits": "Rs. 50,000 per year for girls in technical education (degree/diploma)", "description": "AICTE scholarship for girl students pursuing technical education to promote women in STEM fields.", "source_url": "https://www.aicte-india.org", "source_type": "portal"},
    {"name": "National Means-cum-Merit Scholarship", "slug": "national-means-merit-scholarship", "state": "Central", "category": ["Education", "Scholarship", "Merit"], "ministry": "Ministry of Education", "benefits": "Rs. 12,000 per year for meritorious students from economically weaker sections for Class 9-12", "description": "Awards scholarships to meritorious students of economically weaker sections to arrest their dropout at class 8.", "source_url": "https://scholarships.gov.in", "source_type": "portal"},

    # ═══════════ CENTRAL — HEALTH ═══════════
    {"name": "Ayushman Bharat PM-JAY", "slug": "ayushman-bharat-pmjay", "state": "Central", "category": ["Health", "Insurance", "BPL"], "ministry": "Ministry of Health", "benefits": "Rs. 5,00,000 health cover per family per year for secondary and tertiary hospitalization", "description": "World's largest health insurance scheme covering 12 crore poor families with cashless treatment at empanelled hospitals.", "source_url": "https://pmjay.gov.in", "source_type": "portal"},
    {"name": "Janani Suraksha Yojana", "slug": "janani-suraksha-yojana", "state": "Central", "category": ["Health", "Maternity", "Women"], "ministry": "Ministry of Health", "benefits": "Rs. 1,400 (rural) / Rs. 1,000 (urban) cash assistance for institutional delivery", "description": "Safe motherhood intervention promoting institutional delivery among poor pregnant women for reducing maternal and neonatal mortality.", "source_url": "https://nhm.gov.in", "source_type": "html"},
    {"name": "Pradhan Mantri Surakshit Matritva Abhiyan", "slug": "pm-surakshit-matritva-abhiyan", "state": "Central", "category": ["Health", "Maternity", "Pregnancy"], "ministry": "Ministry of Health", "benefits": "Free antenatal checkups on 9th of every month at government health facilities", "description": "Provides free comprehensive and quality antenatal care to pregnant women on the 9th of every month.", "source_url": "https://pmsma.nhp.gov.in", "source_type": "portal"},
    {"name": "Mission Indradhanush (Immunization)", "slug": "mission-indradhanush", "state": "Central", "category": ["Health", "Immunization", "Children"], "ministry": "Ministry of Health", "benefits": "Free immunization for all children under 2 years and pregnant women", "description": "Aims to achieve full immunization coverage for all children and pregnant women through intensive immunization drives.", "source_url": "https://nhm.gov.in", "source_type": "html"},
    {"name": "National Health Mission", "slug": "national-health-mission", "state": "Central", "category": ["Health", "Rural", "Primary"], "ministry": "Ministry of Health", "benefits": "Free primary healthcare, medicines, diagnostics at government health centres", "description": "Strengthens health systems to provide accessible, affordable, and quality healthcare, especially to rural and vulnerable populations.", "source_url": "https://nhm.gov.in", "source_type": "portal"},
    {"name": "PM National Dialysis Programme", "slug": "pm-national-dialysis-programme", "state": "Central", "category": ["Health", "Kidney", "Dialysis"], "ministry": "Ministry of Health", "benefits": "Free dialysis services at district hospitals for BPL patients", "description": "Provides free dialysis services to poor patients at district hospitals through PPP model.", "source_url": "https://nhm.gov.in", "source_type": "html"},
    {"name": "Rashtriya Swasthya Bima Yojana", "slug": "rashtriya-swasthya-bima-yojana", "state": "Central", "category": ["Health", "Insurance", "BPL"], "ministry": "Ministry of Labour", "benefits": "Health insurance of Rs. 30,000 per year for BPL families", "description": "Health insurance scheme for BPL families in the unorganized sector providing cashless hospitalization up to Rs. 30,000.", "source_url": "https://labour.gov.in", "source_type": "html"},

    # ═══════════ CENTRAL — HOUSING ═══════════
    {"name": "PM Awas Yojana Gramin", "slug": "pm-awas-yojana-gramin", "state": "Central", "category": ["Housing", "Rural", "BPL"], "ministry": "Ministry of Rural Development", "benefits": "Rs. 1,20,000 (plains) / Rs. 1,30,000 (hills) for pucca house construction", "description": "Provides financial assistance for construction of pucca houses to all houseless and those living in kutcha/dilapidated houses.", "source_url": "https://pmayg.nic.in", "source_type": "portal"},
    {"name": "PM Awas Yojana Urban", "slug": "pm-awas-yojana-urban", "state": "Central", "category": ["Housing", "Urban"], "ministry": "Ministry of Housing", "benefits": "Interest subsidy of 6.5% on home loans for EWS/LIG, CLSS up to Rs. 2.67 lakhs", "description": "Affordable housing for urban poor through Credit Linked Subsidy, in-situ slum redevelopment, and affordable housing partnerships.", "source_url": "https://pmay-urban.gov.in", "source_type": "portal"},
    {"name": "Indira Awaas Yojana (IAY)", "slug": "indira-awaas-yojana", "state": "Central", "category": ["Housing", "Rural", "SC/ST"], "ministry": "Ministry of Rural Development", "benefits": "Housing assistance for BPL families in rural areas", "description": "Legacy housing scheme for rural BPL families, now subsumed under PMAY-G but still active in some states.", "source_url": "https://pmayg.nic.in", "source_type": "portal"},

    # ═══════════ CENTRAL — WOMEN & CHILD ═══════════
    {"name": "PM Ujjwala Yojana", "slug": "pm-ujjwala-yojana", "state": "Central", "category": ["Women", "BPL", "LPG"], "ministry": "Ministry of Petroleum", "benefits": "Free LPG connection + Rs. 1,600 subsidy + first refill and stove free", "description": "Free LPG connections to women from BPL households to reduce health hazards from unclean cooking fuels.", "source_url": "https://www.pmujjwalayojana.com", "source_type": "portal"},
    {"name": "Sukanya Samriddhi Yojana", "slug": "sukanya-samriddhi-yojana", "state": "Central", "category": ["Girl Child", "Savings", "Tax Benefit"], "ministry": "Ministry of Finance", "benefits": "High interest (8.2%), tax-free returns, min Rs. 250/year, matures at 21", "description": "Government-backed savings scheme for girl child. Parents can open for daughter below 10 years.", "source_url": "https://www.india.gov.in/sukanya-samriddhi-yojana", "source_type": "portal"},
    {"name": "PM Matru Vandana Yojana", "slug": "pm-matru-vandana-yojana", "state": "Central", "category": ["Women", "Maternity", "Cash Transfer"], "ministry": "Ministry of WCD", "benefits": "Rs. 5,000 in 3 instalments for first live birth + Rs. 1,000 for institutional delivery", "description": "Cash incentive for pregnant and lactating mothers for first child to compensate wage loss during pregnancy.", "source_url": "https://wcd.nic.in/schemes/pradhan-mantri-matru-vandana-yojana", "source_type": "html"},
    {"name": "One Stop Centre (Sakhi)", "slug": "one-stop-centre-sakhi", "state": "Central", "category": ["Women", "Safety", "Support"], "ministry": "Ministry of WCD", "benefits": "24/7 shelter, legal aid, medical assistance, counselling for women in distress", "description": "Provides integrated support and assistance to women affected by violence in private and public spaces.", "source_url": "https://wcd.nic.in/schemes/one-stop-centre-scheme-1", "source_type": "html"},
    {"name": "Mahila Shakti Kendra", "slug": "mahila-shakti-kendra", "state": "Central", "category": ["Women", "Empowerment"], "ministry": "Ministry of WCD", "benefits": "Community engagement, awareness, and skill development for rural women", "description": "Provides interface for rural women to approach government for services through community outreach.", "source_url": "https://wcd.nic.in", "source_type": "html"},
    {"name": "ICDS Anganwadi Services", "slug": "icds-anganwadi-services", "state": "Central", "category": ["Children", "Nutrition", "Women"], "ministry": "Ministry of WCD", "benefits": "Supplementary nutrition, immunization, health checkups, pre-school education for children 0-6 years", "description": "Integrated Child Development Services providing nutritional and developmental support through Anganwadi centres.", "source_url": "https://wcd.nic.in/schemes/integrated-child-development-services-scheme", "source_type": "html"},

    # ═══════════ CENTRAL — EMPLOYMENT & SKILLS ═══════════
    {"name": "Skill India - PMKVY", "slug": "skill-india-pmkvy", "state": "Central", "category": ["Skills", "Youth", "Employment"], "ministry": "Ministry of Skill Development", "benefits": "Free skill training + certification + Rs. 8,000 reward on completion", "description": "Free skill training and certification for Indian youth in 40+ sectors to improve employability.", "source_url": "https://www.skillindia.gov.in", "source_type": "portal"},
    {"name": "MGNREGA", "slug": "mgnrega", "state": "Central", "category": ["Employment", "Rural", "Guarantee"], "ministry": "Ministry of Rural Development", "benefits": "100 days guaranteed wage employment per year for rural households at min Rs. 267/day", "description": "Guarantees 100 days of wage employment per year to every rural household whose adult members volunteer for unskilled manual work.", "source_url": "https://nrega.nic.in", "source_type": "portal"},
    {"name": "PM Rojgar Protsahan Yojana", "slug": "pm-rojgar-protsahan-yojana", "state": "Central", "category": ["Employment", "EPFO", "Subsidy"], "ministry": "Ministry of Labour", "benefits": "Government pays employer EPF contribution (12%) for new employees for 3 years", "description": "Incentivizes employers to create new employment by paying employer EPF contribution for new employees.", "source_url": "https://labour.gov.in", "source_type": "html"},
    {"name": "Deen Dayal Upadhyaya Grameen Kaushalya Yojana", "slug": "ddu-gky", "state": "Central", "category": ["Skills", "Rural", "Youth"], "ministry": "Ministry of Rural Development", "benefits": "Free residential skill training + placement assistance for rural poor youth", "description": "Skill training and placement programme for rural poor youth aged 15-35 to transform them into economically productive citizens.", "source_url": "https://ddugky.gov.in", "source_type": "portal"},
    {"name": "National Apprenticeship Promotion Scheme", "slug": "national-apprenticeship-promotion", "state": "Central", "category": ["Skills", "Apprenticeship"], "ministry": "Ministry of Skill Development", "benefits": "25% stipend sharing by government (up to Rs. 1,500/month) for apprentices", "description": "Promotes apprenticeship training by sharing 25% of prescribed stipend for apprentices in eligible establishments.", "source_url": "https://msde.gov.in", "source_type": "html"},

    # ═══════════ CENTRAL — BUSINESS & MSME ═══════════
    {"name": "PM Mudra Yojana", "slug": "pm-mudra-yojana", "state": "Central", "category": ["Business", "Loan", "MSME"], "ministry": "Ministry of Finance", "benefits": "Collateral-free loans: Shishu (up to 50K), Kishore (50K-5L), Tarun (5L-10L)", "description": "Loans up to Rs. 10 lakhs to non-corporate small/micro enterprises without collateral through banks and NBFCs.", "source_url": "https://www.mudra.org.in", "source_type": "portal"},
    {"name": "Stand Up India", "slug": "stand-up-india", "state": "Central", "category": ["Business", "SC/ST", "Women"], "ministry": "Ministry of Finance", "benefits": "Bank loans between Rs. 10 lakhs to Rs. 1 crore for SC/ST/Women entrepreneurs", "description": "Facilitates bank loans between Rs. 10 lakhs to Rs. 1 crore for at least one SC/ST and one Woman borrower per bank branch.", "source_url": "https://www.standupmitra.in", "source_type": "portal"},
    {"name": "PM Employment Generation Programme", "slug": "pmegp", "state": "Central", "category": ["Business", "MSME", "Subsidy"], "ministry": "Ministry of MSME", "benefits": "Subsidy of 15-35% on project cost for setting up new micro enterprises", "description": "Credit-linked subsidy programme for setting up new micro enterprises in manufacturing and service sectors.", "source_url": "https://msme.gov.in", "source_type": "portal"},
    {"name": "MSME Technology Centre Systems Programme", "slug": "msme-technology-centre", "state": "Central", "category": ["Business", "MSME", "Technology"], "ministry": "Ministry of MSME", "benefits": "Access to advanced technology, testing, training for MSMEs at subsidized rates", "description": "Network of Technology Centres providing testing, training, design, and technology support to MSMEs.", "source_url": "https://msme.gov.in", "source_type": "html"},
    {"name": "Credit Guarantee Fund for MSEs", "slug": "cgtmse", "state": "Central", "category": ["Business", "MSME", "Guarantee"], "ministry": "Ministry of MSME", "benefits": "Collateral-free credit up to Rs. 5 crores for micro and small enterprises", "description": "Provides credit guarantee cover for collateral-free loans extended to MSEs by eligible lending institutions.", "source_url": "https://www.cgtmse.in", "source_type": "portal"},
    {"name": "Startup India", "slug": "startup-india", "state": "Central", "category": ["Business", "Startup", "Innovation"], "ministry": "DPIIT", "benefits": "Tax exemption for 3 years, self-certification, fast-tracked patent applications", "description": "Action plan for startup ecosystem with benefits including tax exemptions, easy compliance, and funding support.", "source_url": "https://www.startupindia.gov.in", "source_type": "portal"},

    # ═══════════ CENTRAL — SOCIAL WELFARE ═══════════
    {"name": "National Social Assistance Programme", "slug": "nsap", "state": "Central", "category": ["Pension", "BPL", "Elderly"], "ministry": "Ministry of Rural Development", "benefits": "Monthly pension: Rs. 200-500 for elderly/widows/disabled BPL persons", "description": "Social pension scheme providing financial assistance to elderly, widows, and disabled persons from BPL families.", "source_url": "https://nsap.nic.in", "source_type": "portal"},
    {"name": "Indira Gandhi National Old Age Pension", "slug": "ignoaps", "state": "Central", "category": ["Pension", "Elderly", "BPL"], "ministry": "Ministry of Rural Development", "benefits": "Rs. 200/month (60-79 years), Rs. 500/month (80+ years) for BPL elderly", "description": "Monthly pension for BPL persons aged 60 and above under National Social Assistance Programme.", "source_url": "https://nsap.nic.in", "source_type": "portal"},
    {"name": "Indira Gandhi National Widow Pension", "slug": "ignwps", "state": "Central", "category": ["Pension", "Widows", "BPL"], "ministry": "Ministry of Rural Development", "benefits": "Rs. 300/month for BPL widows aged 40-79 years", "description": "Monthly pension for BPL widows under National Social Assistance Programme.", "source_url": "https://nsap.nic.in", "source_type": "portal"},
    {"name": "Indira Gandhi National Disability Pension", "slug": "igndps", "state": "Central", "category": ["Pension", "Disabled", "BPL"], "ministry": "Ministry of Rural Development", "benefits": "Rs. 300/month for BPL persons with severe disabilities (80%+)", "description": "Monthly pension for BPL persons with severe disabilities aged 18-79 years.", "source_url": "https://nsap.nic.in", "source_type": "portal"},
    {"name": "National Family Benefit Scheme", "slug": "nfbs", "state": "Central", "category": ["Death Benefit", "BPL"], "ministry": "Ministry of Rural Development", "benefits": "Lump sum Rs. 20,000 on death of primary breadwinner in BPL family", "description": "Lump sum assistance to BPL family on death of the primary breadwinner aged 18-59.", "source_url": "https://nsap.nic.in", "source_type": "portal"},
    {"name": "PM Jeevan Jyoti Bima Yojana", "slug": "pmjjby", "state": "Central", "category": ["Insurance", "Life"], "ministry": "Ministry of Finance", "benefits": "Rs. 2 lakh life insurance cover at premium of Rs. 436/year", "description": "Low-cost life insurance scheme providing Rs. 2 lakh death cover for all bank account holders aged 18-50.", "source_url": "https://jansuraksha.gov.in", "source_type": "portal"},
    {"name": "PM Suraksha Bima Yojana", "slug": "pmsby", "state": "Central", "category": ["Insurance", "Accident"], "ministry": "Ministry of Finance", "benefits": "Rs. 2 lakh accidental death, Rs. 1 lakh partial disability at Rs. 20/year premium", "description": "Low-cost accident insurance scheme for bank account holders aged 18-70 at just Rs. 20 per year.", "source_url": "https://jansuraksha.gov.in", "source_type": "portal"},
    {"name": "Atal Pension Yojana", "slug": "atal-pension-yojana", "state": "Central", "category": ["Pension", "Unorganized"], "ministry": "Ministry of Finance", "benefits": "Guaranteed pension of Rs. 1,000-5,000 per month after age 60", "description": "Pension scheme for workers in unorganized sector with guaranteed monthly pension varying with contribution.", "source_url": "https://jansuraksha.gov.in", "source_type": "portal"},
    {"name": "PM Jan Dhan Yojana", "slug": "pm-jan-dhan-yojana", "state": "Central", "category": ["Banking", "Financial Inclusion"], "ministry": "Ministry of Finance", "benefits": "Zero-balance bank account + RuPay card + Rs. 10,000 OD + Rs. 2L accident cover", "description": "Financial inclusion programme providing universal access to banking with zero-balance accounts, insurance, and overdraft.", "source_url": "https://pmjdy.gov.in", "source_type": "portal"},

    # ═══════════ CENTRAL — SC/ST WELFARE ═══════════
    {"name": "Post-Matric Scholarship for SC", "slug": "post-matric-scholarship-sc", "state": "Central", "category": ["Education", "Scholarship", "SC"], "ministry": "Ministry of Social Justice", "benefits": "Full tuition fees + maintenance allowance for SC students in post-matric education", "description": "Scholarship for SC students studying at post-matriculation level to complete their education.", "source_url": "https://socialjustice.gov.in", "source_type": "html"},
    {"name": "Post-Matric Scholarship for ST", "slug": "post-matric-scholarship-st", "state": "Central", "category": ["Education", "Scholarship", "ST"], "ministry": "Ministry of Tribal Affairs", "benefits": "Full tuition fees + hostel charges + book allowance for ST students", "description": "Scholarship for ST students to pursue post-matric education including professional and technical courses.", "source_url": "https://tribal.nic.in", "source_type": "html"},
    {"name": "Pre-Matric Scholarship for SC/ST", "slug": "pre-matric-scholarship-sc-st", "state": "Central", "category": ["Education", "Scholarship", "SC", "ST"], "ministry": "Ministry of Social Justice", "benefits": "Rs. 150-750 per month + books/ad-hoc grants for SC/ST students (Class 1-10)", "description": "Financial assistance for SC/ST students studying in Class I to X to reduce dropout rates.", "source_url": "https://socialjustice.gov.in", "source_type": "html"},
    {"name": "Venture Capital Fund for SC", "slug": "venture-capital-fund-sc", "state": "Central", "category": ["Business", "SC", "Startup"], "ministry": "Ministry of Social Justice", "benefits": "Concessional finance up to Rs. 15 crores for SC entrepreneurs, equity/quasi-equity support", "description": "Promotes entrepreneurship among SC community by providing concessional finance to SC entrepreneurs.", "source_url": "https://socialjustice.gov.in", "source_type": "html"},
    {"name": "Free Coaching for SC/ST", "slug": "free-coaching-sc-st", "state": "Central", "category": ["Education", "Coaching", "SC", "ST"], "ministry": "Ministry of Social Justice", "benefits": "Free coaching for competitive exams (UPSC, SSC, Banking) for SC/ST students", "description": "Provides free coaching to SC/ST students for competitive examinations through empanelled coaching centres.", "source_url": "https://socialjustice.gov.in", "source_type": "html"},

    # ═══════════ CENTRAL — MINORITY WELFARE ═══════════
    {"name": "PM Jan Vikas Karyakram", "slug": "pmjvk", "state": "Central", "category": ["Minority", "Development"], "ministry": "Ministry of Minority Affairs", "benefits": "Infrastructure development in minority concentration areas: schools, hospitals, skill centres", "description": "Development programme for minority concentration areas covering education, health, skill development infrastructure.", "source_url": "https://minorityaffairs.gov.in", "source_type": "html"},
    {"name": "Maulana Azad National Fellowship", "slug": "maulana-azad-fellowship", "state": "Central", "category": ["Education", "Minority", "Fellowship"], "ministry": "Ministry of Minority Affairs", "benefits": "Rs. 31,000/month (JRF) and Rs. 35,000/month (SRF) for minority M.Phil/Ph.D students", "description": "Fellowship for minority community students to pursue M.Phil and Ph.D in universities/institutions.", "source_url": "https://minorityaffairs.gov.in", "source_type": "html"},
    {"name": "Nai Roshni (Leadership for Minority Women)", "slug": "nai-roshni", "state": "Central", "category": ["Women", "Minority", "Training"], "ministry": "Ministry of Minority Affairs", "benefits": "6-day leadership training + Rs. 3,000 assistance for minority women", "description": "Leadership development programme for minority women to enable them to emerge as community leaders.", "source_url": "https://minorityaffairs.gov.in", "source_type": "html"},

    # ═══════════ CENTRAL — INFRASTRUCTURE ═══════════
    {"name": "PM Gram Sadak Yojana", "slug": "pmgsy", "state": "Central", "category": ["Rural", "Roads", "Infrastructure"], "ministry": "Ministry of Rural Development", "benefits": "All-weather road connectivity to unconnected habitations with 500+ population", "description": "Provides all-weather road connectivity to eligible unconnected habitations in rural areas.", "source_url": "https://pmgsy.nic.in", "source_type": "portal"},
    {"name": "Jal Jeevan Mission", "slug": "jal-jeevan-mission", "state": "Central", "category": ["Water", "Rural", "Tap"], "ministry": "Jal Shakti Ministry", "benefits": "Functional tap water connection to every rural household by 2024", "description": "Aims to provide functional household tap connection to every rural household for drinking water.", "source_url": "https://jaljeevanmission.gov.in", "source_type": "portal"},
    {"name": "Swachh Bharat Mission Gramin", "slug": "swachh-bharat-gramin", "state": "Central", "category": ["Sanitation", "Rural", "Toilet"], "ministry": "Jal Shakti Ministry", "benefits": "Rs. 12,000 incentive for construction of household toilet in rural areas", "description": "Aims to make India open-defecation free by providing incentives for household toilet construction.", "source_url": "https://sbm.gov.in", "source_type": "portal"},
    {"name": "PM Sahaj Bijli Har Ghar Yojana (Saubhagya)", "slug": "saubhagya", "state": "Central", "category": ["Electricity", "Rural"], "ministry": "Ministry of Power", "benefits": "Free electricity connection to all un-electrified poor households", "description": "Provides last mile electricity connectivity to all remaining un-electrified households in rural and urban areas.", "source_url": "https://saubhagya.gov.in", "source_type": "portal"},
    {"name": "Digital India", "slug": "digital-india", "state": "Central", "category": ["Digital", "Technology", "Internet"], "ministry": "MeitY", "benefits": "Common Service Centres, BharatNet broadband, digital literacy for rural India", "description": "Flagship programme to transform India into a digitally empowered society and knowledge economy.", "source_url": "https://www.digitalindia.gov.in", "source_type": "portal"},

    # ═══════════ TAMIL NADU — STATE SCHEMES ═══════════
    {"name": "TN CM Marriage Assistance Scheme", "slug": "tn-cm-marriage-assistance", "state": "Tamil Nadu", "category": ["Marriage", "Women", "SC/ST"], "ministry": "Social Welfare Department", "benefits": "Rs. 25,000 marriage assistance + Rs. 50,000 if bride is graduate", "description": "Financial assistance for marriage of daughters from poor SC/ST/BC/MBC families in Tamil Nadu.", "source_url": "https://www.tnsocialwelfare.tn.gov.in", "source_type": "html"},
    {"name": "TN Amma Two Wheeler Scheme", "slug": "tn-amma-two-wheeler", "state": "Tamil Nadu", "category": ["Women", "Transport", "Subsidy"], "ministry": "Tamil Nadu Government", "benefits": "50% subsidy (up to Rs. 25,000) on two-wheelers for working women", "description": "Subsidized two-wheeler scheme for working women in Tamil Nadu to improve mobility and employment access.", "source_url": "https://www.tn.gov.in", "source_type": "html"},
    {"name": "TN Free Laptop Scheme", "slug": "tn-free-laptop-scheme", "state": "Tamil Nadu", "category": ["Education", "Technology"], "ministry": "Tamil Nadu Government", "benefits": "Free laptop for students joining Class 11 and college in government schools", "description": "Distribution of free laptops to students of government and aided schools to bridge the digital divide.", "source_url": "https://www.tn.gov.in", "source_type": "html"},
    {"name": "TN Kalaignar Insurance Scheme", "slug": "tn-kalaignar-insurance", "state": "Tamil Nadu", "category": ["Health", "Insurance"], "ministry": "Tamil Nadu Government", "benefits": "Free medical treatment up to Rs. 5 lakhs for life-threatening diseases at empanelled hospitals", "description": "Health insurance for families earning less than Rs. 72,000/year covering critical illness treatment.", "source_url": "https://www.cmchistn.com", "source_type": "html"},
    {"name": "TN Uzhavar Sandhai", "slug": "tn-uzhavar-sandhai", "state": "Tamil Nadu", "category": ["Agriculture", "Market", "Farmers"], "ministry": "Tamil Nadu Agriculture", "benefits": "Direct farmer-to-consumer markets eliminating middlemen", "description": "Government-run farmers markets where farmers sell produce directly to consumers at fair prices.", "source_url": "https://www.tn.gov.in/department/2", "source_type": "html"},
    {"name": "TN Free Bus Pass for Students", "slug": "tn-free-bus-pass-students", "state": "Tamil Nadu", "category": ["Education", "Transport"], "ministry": "Tamil Nadu Government", "benefits": "Free bus pass for all school and college students in government buses", "description": "Free travel in government buses for students to reduce education costs and improve access.", "source_url": "https://www.tn.gov.in", "source_type": "html"},
    {"name": "TN Pudhumai Penn Scheme", "slug": "tn-pudhumai-penn", "state": "Tamil Nadu", "category": ["Education", "Women", "Stipend"], "ministry": "Tamil Nadu Government", "benefits": "Rs. 1,000 per month stipend for girls from government school backgrounds pursuing higher education", "description": "Monthly stipend for girl students who studied in government schools to pursue graduation and professional courses.", "source_url": "https://www.tn.gov.in", "source_type": "html"},
    {"name": "TN Adi Dravidar Housing", "slug": "tn-adi-dravidar-housing", "state": "Tamil Nadu", "category": ["Housing", "SC/ST"], "ministry": "Adi Dravidar Welfare", "benefits": "Rs. 2,50,000 for construction of new house for SC/ST families", "description": "Housing assistance for Adi Dravidar and Tribal communities in Tamil Nadu.", "source_url": "https://www.adwelfare.tn.gov.in", "source_type": "html"},
    {"name": "TN Old Age Pension", "slug": "tn-old-age-pension", "state": "Tamil Nadu", "category": ["Pension", "Elderly"], "ministry": "Tamil Nadu Government", "benefits": "Rs. 1,000 per month pension for destitute elderly persons", "description": "Monthly pension for elderly persons above 60 years with no regular income in Tamil Nadu.", "source_url": "https://www.tnsocialwelfare.tn.gov.in", "source_type": "html"},
    {"name": "TN Differently Abled Pension", "slug": "tn-differently-abled-pension", "state": "Tamil Nadu", "category": ["Pension", "Disabled"], "ministry": "Tamil Nadu Government", "benefits": "Rs. 1,500 per month for persons with 40%+ disability", "description": "Monthly pension for differently abled persons in Tamil Nadu with disability certificate.", "source_url": "https://www.tnsocialwelfare.tn.gov.in", "source_type": "html"},
    {"name": "TN BC/MBC Free Education", "slug": "tn-bc-mbc-free-education", "state": "Tamil Nadu", "category": ["Education", "BC/MBC"], "ministry": "BC/MBC Welfare", "benefits": "Fee concession, hostel facility, and special coaching for BC/MBC students", "description": "Educational support for Backward Classes and Most Backward Classes students in Tamil Nadu.", "source_url": "https://bcmbcmw.tn.gov.in", "source_type": "html"},

    # ═══════════ KERALA — STATE SCHEMES ═══════════
    {"name": "Kerala NORKA Pravasi Welfare", "slug": "kerala-norka-pravasi-welfare", "state": "Kerala", "category": ["NRI", "Welfare", "Returnees"], "ministry": "NORKA Department", "benefits": "Rehabilitation assistance, education support, medical aid, pension for returned emigrants", "description": "Welfare schemes for Keralite emigrants including return and reintegration assistance.", "source_url": "https://www.norkaroots.org", "source_type": "html"},
    {"name": "Kerala Karunya Health Scheme", "slug": "kerala-karunya-health", "state": "Kerala", "category": ["Health", "Insurance"], "ministry": "Kerala Government", "benefits": "Financial assistance up to Rs. 5 lakhs for treatment of critical illnesses for BPL families", "description": "Health protection scheme for BPL families in Kerala covering critical illness treatment costs.", "source_url": "http://sjd.kerala.gov.in", "source_type": "html"},
    {"name": "Kerala Snehapoorvam", "slug": "kerala-snehapoorvam", "state": "Kerala", "category": ["Children", "Orphan", "Education"], "ministry": "Kerala SJD", "benefits": "Rs. 300-500 per month educational assistance for orphan children", "description": "Monthly educational assistance for orphan children in Kerala to continue their studies.", "source_url": "http://sjd.kerala.gov.in", "source_type": "html"},
    {"name": "Kerala Ashraya Housing", "slug": "kerala-ashraya-housing", "state": "Kerala", "category": ["Housing", "BPL"], "ministry": "Kerala Rural Development", "benefits": "Rs. 3,00,000 for house construction for homeless BPL families", "description": "Comprehensive housing scheme for destitute and homeless families identified through Ashraya survey.", "source_url": "http://lsgkerala.gov.in", "source_type": "html"},
    {"name": "Kerala Welfare Pension", "slug": "kerala-welfare-pension", "state": "Kerala", "category": ["Pension", "Elderly", "Widow"], "ministry": "Kerala Government", "benefits": "Rs. 1,600 per month pension for elderly, widows, and disabled persons", "description": "Social security pension for eligible elderly, widows, differently abled, and unmarried women in Kerala.", "source_url": "http://sjd.kerala.gov.in", "source_type": "html"},
    {"name": "Kerala KITE Digital Education", "slug": "kerala-kite-digital-education", "state": "Kerala", "category": ["Education", "Digital", "Technology"], "ministry": "Kerala IT Mission", "benefits": "Free laptops, digital classrooms, IT@School programme for government school students", "description": "Digital education initiative providing ICT-enabled education in all government and aided schools in Kerala.", "source_url": "https://kite.kerala.gov.in", "source_type": "html"},
    {"name": "Kerala Fishermen Insurance", "slug": "kerala-fishermen-insurance", "state": "Kerala", "category": ["Insurance", "Fishermen"], "ministry": "Kerala Fisheries", "benefits": "Rs. 5 lakh insurance cover for fishermen at subsidized premium", "description": "Insurance coverage for traditional fishermen in Kerala covering accidental death and disability.", "source_url": "http://fisheries.kerala.gov.in", "source_type": "html"},

    # ═══════════ OTHER STATES — TIER 2 ═══════════
    {"name": "AP YSR Rythu Bharosa", "slug": "ap-ysr-rythu-bharosa", "state": "Andhra Pradesh", "category": ["Agriculture", "Farmers", "Income Support"], "ministry": "AP Agriculture", "benefits": "Rs. 13,500 per year investment support for every farmer family", "description": "Input subsidy for farmers in Andhra Pradesh to be used for crop investment at the start of each season.", "source_url": "https://navasakam.ap.gov.in", "source_type": "html"},
    {"name": "AP YSR Aarogyasri", "slug": "ap-ysr-aarogyasri", "state": "Andhra Pradesh", "category": ["Health", "Insurance"], "ministry": "AP Government", "benefits": "Free treatment up to Rs. 5 lakhs per family per year for BPL families", "description": "Health insurance scheme for families earning less than Rs. 5 lakhs providing cashless treatment at network hospitals.", "source_url": "https://www.aarogyasri.telangana.gov.in", "source_type": "html"},
    {"name": "AP Amma Vodi", "slug": "ap-amma-vodi", "state": "Andhra Pradesh", "category": ["Education", "Women"], "ministry": "AP Government", "benefits": "Rs. 15,000 per year for mothers/guardians who send children to school", "description": "Cash incentive to mothers to ensure their children attend school regularly and reduce dropout rates.", "source_url": "https://navasakam.ap.gov.in", "source_type": "html"},
    {"name": "Karnataka Bhagyalakshmi Scheme", "slug": "karnataka-bhagyalakshmi", "state": "Karnataka", "category": ["Girl Child", "BPL"], "ministry": "Karnataka WCD", "benefits": "Rs. 2,00,000 deposited in name of girl child from BPL family, matured at 18", "description": "Bond scheme for girl children from BPL families with maturity amount available at age 18.", "source_url": "https://sevasindhu.karnataka.gov.in", "source_type": "portal"},
    {"name": "Karnataka Anna Bhagya", "slug": "karnataka-anna-bhagya", "state": "Karnataka", "category": ["Food", "BPL", "Ration"], "ministry": "Karnataka Government", "benefits": "10 kg free rice per person per month for BPL families", "description": "Free rice distribution scheme for BPL families in Karnataka ensuring food security.", "source_url": "https://ahara.kar.nic.in", "source_type": "portal"},
    {"name": "MH Majhi Kanya Bhagyashree", "slug": "mh-majhi-kanya-bhagyashree", "state": "Maharashtra", "category": ["Girl Child", "Insurance"], "ministry": "Maharashtra WCD", "benefits": "Rs. 50,000 insurance + savings for girl child from BPL families on 18th birthday", "description": "Encourages families to have girl children by providing insurance and savings benefit.", "source_url": "https://womenchild.maharashtra.gov.in", "source_type": "html"},
    {"name": "UP Kanya Sumangala Yojana", "slug": "up-kanya-sumangala-yojana", "state": "Uttar Pradesh", "category": ["Girl Child", "Education"], "ministry": "UP Government", "benefits": "Rs. 15,000 in 6 instalments from birth to graduation for girls from BPL families", "description": "Financial assistance for girl children from birth to graduation to promote girl child education in UP.", "source_url": "https://mksy.up.gov.in", "source_type": "portal"},
    {"name": "Rajasthan Chiranjeevi Health Insurance", "slug": "rajasthan-chiranjeevi", "state": "Rajasthan", "category": ["Health", "Insurance"], "ministry": "Rajasthan Government", "benefits": "Rs. 25 lakhs health insurance per family per year at Rs. 850/year premium", "description": "Universal health insurance scheme for all families in Rajasthan with Rs. 25 lakh cover.", "source_url": "https://chiranjeevi.rajasthan.gov.in", "source_type": "portal"},
    {"name": "Rajasthan Palanhar Yojana", "slug": "rajasthan-palanhar", "state": "Rajasthan", "category": ["Children", "Orphan", "Welfare"], "ministry": "Rajasthan SJE", "benefits": "Rs. 500-1,000 per month + Rs. 2,000 annual clothing for orphan children", "description": "Monthly assistance for maintenance of orphan children being raised by relatives or foster parents.", "source_url": "https://sje.rajasthan.gov.in", "source_type": "html"},

    # ═══════════ CENTRAL — ADDITIONAL ═══════════
    {"name": "PM SVANidhi (Street Vendor)", "slug": "pm-svanidhi", "state": "Central", "category": ["Business", "Street Vendor", "Loan"], "ministry": "Ministry of Housing", "benefits": "Small loans: Rs. 10,000 (1st), Rs. 20,000 (2nd), Rs. 50,000 (3rd) + 7% interest subsidy + cashback", "description": "Micro-credit facility for street vendors affected by COVID to resume livelihoods.", "source_url": "https://pmsvanidhi.mohua.gov.in", "source_type": "portal"},
    {"name": "PM Garib Kalyan Anna Yojana", "slug": "pmgkay", "state": "Central", "category": ["Food", "BPL", "Free"], "ministry": "Ministry of Consumer Affairs", "benefits": "5 kg free foodgrain per person per month for 80 crore beneficiaries", "description": "Free foodgrain (rice/wheat) distribution to all NFSA beneficiaries ensuring zero hunger.", "source_url": "https://dfpd.gov.in", "source_type": "portal"},
    {"name": "Ujjwala 2.0 Refill Subsidy", "slug": "ujjwala-2-refill", "state": "Central", "category": ["Women", "LPG", "Subsidy"], "ministry": "Ministry of Petroleum", "benefits": "Subsidy of Rs. 200 per LPG refill for up to 12 refills per year for Ujjwala beneficiaries", "description": "Extended subsidy on LPG refills for Ujjwala beneficiaries to ensure continued clean cooking.", "source_url": "https://www.pmujjwalayojana.com", "source_type": "portal"},
    {"name": "PMAY Interest Subsidy for EWS/LIG", "slug": "pmay-clss", "state": "Central", "category": ["Housing", "Urban", "Subsidy"], "ministry": "Ministry of Housing", "benefits": "Interest subsidy of 6.5% on home loans up to Rs. 6 lakhs for 20 years", "description": "Credit-Linked Subsidy Scheme under PMAY-Urban for economically weaker and lower income groups.", "source_url": "https://pmay-urban.gov.in", "source_type": "portal"},
    {"name": "Senior Citizen Saving Scheme", "slug": "scss", "state": "Central", "category": ["Savings", "Elderly", "Tax Benefit"], "ministry": "Ministry of Finance", "benefits": "8.2% interest rate, tax benefit under 80C, investment up to Rs. 30 lakhs", "description": "Government-backed savings scheme for senior citizens (60+) with high interest rates and tax benefits.", "source_url": "https://www.india.gov.in", "source_type": "portal"},
    {"name": "PM Vishwakarma Yojana", "slug": "pm-vishwakarma", "state": "Central", "category": ["Artisan", "Skill", "Loan"], "ministry": "Ministry of MSME", "benefits": "Rs. 15,000 toolkit + skill training + Rs. 1-2 lakh loan at 5% + digital incentive", "description": "Comprehensive support for traditional artisans and craftspeople including training, tools, credit, and digital empowerment.", "source_url": "https://pmvishwakarma.gov.in", "source_type": "portal"},
    {"name": "Atmanirbhar Bharat Rojgar Yojana", "slug": "abry", "state": "Central", "category": ["Employment", "EPFO"], "ministry": "Ministry of Labour", "benefits": "Government pays both employer and employee EPF contribution for new employees for 2 years", "description": "Incentivizes creation of new employment by bearing EPF cost for new employees earning up to Rs. 15,000/month.", "source_url": "https://labour.gov.in", "source_type": "html"},
    {"name": "National Rural Livelihood Mission", "slug": "nrlm-dday", "state": "Central", "category": ["Rural", "SHG", "Livelihood"], "ministry": "Ministry of Rural Development", "benefits": "SHG formation + bank linkage + Rs. 15,000 revolving fund + skill training", "description": "Promotes self-employment and organization of rural poor into SHGs for sustainable livelihood enhancement.", "source_url": "https://nrlm.gov.in", "source_type": "portal"},
    {"name": "DigiLocker", "slug": "digilocker", "state": "Central", "category": ["Digital", "Documents"], "ministry": "MeitY", "benefits": "Free cloud storage for government-issued documents, digital verification", "description": "Digital platform for issuance and verification of government documents, eliminating use of physical documents.", "source_url": "https://www.digilocker.gov.in", "source_type": "portal"},
    {"name": "e-Shram Card (Unorganized Workers)", "slug": "e-shram-card", "state": "Central", "category": ["Labour", "Unorganized", "Registration"], "ministry": "Ministry of Labour", "benefits": "Registration + Rs. 2 lakh accidental insurance + access to government welfare schemes", "description": "National database of unorganized workers providing them unique ID and access to social security benefits.", "source_url": "https://eshram.gov.in", "source_type": "portal"},
    {"name": "PM CARES for Children", "slug": "pm-cares-children", "state": "Central", "category": ["Children", "Orphan", "COVID"], "ministry": "PMO", "benefits": "Rs. 10 lakh corpus at 18 years + free education + health insurance for COVID orphans", "description": "Support for children who lost parents to COVID-19 including education, health, and financial corpus.", "source_url": "https://pmcaresforchildren.in", "source_type": "portal"},
]


def seed_all_schemes():
    """Seed all schemes into the database with deduplication."""
    client = get_supabase_client()
    embedder = get_embedding_client()

    # Combine base + extra schemes
    ALL_SCHEMES = SCHEMES + EXTRA_SCHEMES
    logger.info(f"🌱 Starting seed: {len(ALL_SCHEMES)} schemes to process ({len(SCHEMES)} base + {len(EXTRA_SCHEMES)} extra)")

    inserted = 0
    updated = 0
    skipped = 0
    errors = 0

    for i, scheme in enumerate(ALL_SCHEMES):
        try:
            slug = scheme["slug"]

            # Convert documents_required from string to array if needed (DB expects text[])
            if isinstance(scheme.get("documents_required"), str):
                scheme["documents_required"] = [
                    d.strip() for d in scheme["documents_required"].split(",") if d.strip()
                ]

            # Check if exists
            existing = client.table("schemes").select("id").eq("slug", slug).execute()

            if existing.data:
                # Already exists — UPDATE with new/enriched fields only
                scheme_id = existing.data[0]["id"]
                update_fields = {}
                # Only update fields that have new data in the seed
                for field in ["eligibility", "application_mode", "source_url", "benefits", "description", "documents_required"]:
                    if scheme.get(field):
                        update_fields[field] = scheme[field]
                if update_fields:
                    client.table("schemes").update(update_fields).eq("id", scheme_id).execute()
                    updated += 1
                else:
                    skipped += 1
                # Re-generate embedding with enriched text
            else:
                # Insert new scheme
                result = client.table("schemes").insert(scheme).execute()
                scheme_id = result.data[0]["id"] if result.data else None
                if scheme_id:
                    inserted += 1
                else:
                    errors += 1
                    continue

            # Generate/regenerate embedding for this scheme (both new and updated)
            embed_text = (
                f"{scheme['name']}. "
                f"{scheme.get('description', '')} "
                f"Benefits: {scheme.get('benefits', '')}. "
                f"Category: {', '.join(scheme.get('category', []))}. "
                f"State: {scheme.get('state', 'Central')}. "
                f"Ministry: {scheme.get('ministry', '')}."
            )
            # Add eligibility and application info for richer embeddings
            if scheme.get("eligibility"):
                embed_text += f" Eligibility: {scheme['eligibility']}."
            if scheme.get("source_url"):
                embed_text += f" Apply at: {scheme['source_url']}."
            if scheme.get("application_mode"):
                embed_text += f" Application mode: {scheme['application_mode']}."
            if scheme.get("documents_required"):
                docs = scheme["documents_required"]
                if isinstance(docs, list):
                    docs = ", ".join(docs)
                embed_text += f" Documents: {docs}."

            embedding = embedder.embed_text(embed_text)

            # Delete old embeddings for this scheme (upsert pattern)
            try:
                client.table("scheme_embeddings").delete().eq("scheme_id", scheme_id).execute()
            except Exception:
                pass  # May not exist yet

            client.table("scheme_embeddings").insert({
                "scheme_id": scheme_id,
                "chunk_text": embed_text,
                "chunk_index": 0,
                "embedding": embedding,
                "metadata": {
                    "source": "seed_script",
                    "seeded_at": "2026-02-17",
                },
            }).execute()

            if (i + 1) % 20 == 0:
                logger.info(f"  Progress: {i+1}/{len(ALL_SCHEMES)} schemes processed...")

        except Exception as e:
            errors += 1
            logger.error(f"Failed to seed '{scheme.get('name', '?')}': {e}")

    logger.info(
        f"\n🌱 Seed complete!\n"
        f"  ✅ Inserted: {inserted}\n"
        f"  🔄 Updated: {updated}\n"
        f"  ⏭️  Skipped: {skipped}\n"
        f"  ❌ Errors: {errors}\n"
        f"  📊 Total processed: {inserted + updated + skipped}"
    )

    return {"inserted": inserted, "updated": updated, "skipped": skipped, "errors": errors}


if __name__ == "__main__":
    seed_all_schemes()
