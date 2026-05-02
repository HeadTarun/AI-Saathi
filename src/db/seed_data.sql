-- ============================================================
-- SEED: Exams
-- ============================================================
INSERT INTO exams (name, description, syllabus_version) VALUES
('SSC CGL', 'Staff Selection Commission Combined Graduate Level', '2024'),
('SBI PO', 'State Bank of India Probationary Officer', '2024')
ON CONFLICT (name) DO NOTHING;

-- ============================================================
-- SEED: SSC CGL Syllabus Topics (Quantitative Aptitude)
-- ============================================================
-- Get exam_id first: SELECT id FROM exams WHERE name='SSC CGL';
-- Replace <ssc_exam_id> with actual UUID after running above query,
-- OR use a DO block as shown below.

DO $$
DECLARE
    ssc_id UUID;
    sbi_id UUID;
BEGIN
    SELECT id INTO ssc_id FROM exams WHERE name='SSC CGL';
    SELECT id INTO sbi_id FROM exams WHERE name='SBI PO';

    -- Quantitative Aptitude topics for SSC CGL
    INSERT INTO syllabus_topics
        (exam_id, subject, topic_name, subtopics, difficulty, priority, estimated_hours)
    VALUES
    (ssc_id, 'Quantitative Aptitude', 'Number System',
     ARRAY['Natural Numbers','Integers','LCM & HCF','Divisibility Rules','Remainders'],
     2, 'HIGH', 3.0),

    (ssc_id, 'Quantitative Aptitude', 'Percentage',
     ARRAY['Basic Percentage','Percentage Increase/Decrease','Successive Changes','Percentage to Fraction'],
     2, 'HIGH', 2.5),

    (ssc_id, 'Quantitative Aptitude', 'Ratio & Proportion',
     ARRAY['Ratio Basics','Proportion','Direct/Inverse Variation','Partnership'],
     2, 'HIGH', 2.0),

    (ssc_id, 'Quantitative Aptitude', 'Simple & Compound Interest',
     ARRAY['SI Formula','CI Formula','Difference between SI and CI','Population Growth'],
     3, 'HIGH', 2.5),

    (ssc_id, 'Quantitative Aptitude', 'Profit & Loss',
     ARRAY['Cost Price','Selling Price','Profit %','Loss %','Discount','Marked Price','Successive Discounts'],
     3, 'HIGH', 3.0),

    (ssc_id, 'Quantitative Aptitude', 'Time & Work',
     ARRAY['Basic Time-Work','Work Efficiency','Pipes & Cisterns','MDH Formula'],
     3, 'HIGH', 3.0),

    (ssc_id, 'Quantitative Aptitude', 'Time Speed Distance',
     ARRAY['Basic TSD','Relative Speed','Trains','Boats & Streams','Circular Motion'],
     4, 'HIGH', 3.5),

    (ssc_id, 'Quantitative Aptitude', 'Data Interpretation',
     ARRAY['Bar Graph','Line Graph','Pie Chart','Table','Mixed DI'],
     4, 'HIGH', 4.0),

    (ssc_id, 'Quantitative Aptitude', 'Algebra',
     ARRAY['Linear Equations','Quadratic Equations','Identities','Polynomials'],
     3, 'MED', 2.5),

    (ssc_id, 'Quantitative Aptitude', 'Geometry',
     ARRAY['Lines & Angles','Triangles','Circles','Quadrilaterals','Area & Perimeter'],
     4, 'MED', 3.5),

    -- Logical Reasoning topics for SSC CGL
    (ssc_id, 'Logical Reasoning', 'Series',
     ARRAY['Number Series','Letter Series','Mixed Series','Missing Term'],
     2, 'HIGH', 2.0),

    (ssc_id, 'Logical Reasoning', 'Puzzles',
     ARRAY['Linear Arrangement','Circular Arrangement','Floor Puzzle','Box Puzzle'],
     4, 'HIGH', 4.0),

    (ssc_id, 'Logical Reasoning', 'Coding-Decoding',
     ARRAY['Letter Coding','Number Coding','Substitution','Mixed Coding'],
     2, 'HIGH', 1.5),

    (ssc_id, 'Logical Reasoning', 'Direction Sense',
     ARRAY['Basic Directions','Distances','Shadow Problems','Turns'],
     2, 'MED', 1.5),

    (ssc_id, 'Logical Reasoning', 'Blood Relations',
     ARRAY['Family Tree','Coded Blood Relations','Mixed Problems'],
     3, 'MED', 1.5),

    (ssc_id, 'Logical Reasoning', 'Seating Arrangement',
     ARRAY['Linear Seating','Circular Seating','Double Row','Parallel Rows'],
     4, 'HIGH', 3.0),

    -- SBI PO topics (same subjects, slightly different priority weights)
    (sbi_id, 'Quantitative Aptitude', 'Data Interpretation',
     ARRAY['Bar Graph','Line Graph','Pie Chart','Caselet DI','Mixed DI'],
     5, 'HIGH', 5.0),

    (sbi_id, 'Quantitative Aptitude', 'Percentage',
     ARRAY['Basic Percentage','Successive Changes','Applications in DI'],
     2, 'HIGH', 2.0),

    (sbi_id, 'Logical Reasoning', 'Puzzles',
     ARRAY['Linear Arrangement','Circular Arrangement','Floor Puzzle','Month-Based Puzzle'],
     5, 'HIGH', 5.0),

    (sbi_id, 'Logical Reasoning', 'Seating Arrangement',
     ARRAY['Linear','Circular','Double Row','Box-Based'],
     5, 'HIGH', 4.0)

    ON CONFLICT DO NOTHING;

END $$;
