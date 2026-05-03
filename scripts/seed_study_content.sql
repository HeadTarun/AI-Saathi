insert into exams (id, name, description, syllabus_version, is_active) values
('exam-ssc-cgl', 'SSC CGL', 'SSC CGL preparation', '2026', true),
('exam-sbi-po', 'SBI PO', 'SBI PO preparation', '2026', true),
('exam-ibps-po', 'IBPS PO', 'IBPS PO preparation', '2026', true)
on conflict (id) do update set
    name = excluded.name,
    description = excluded.description,
    syllabus_version = excluded.syllabus_version,
    is_active = excluded.is_active;

insert into syllabus_topics
(id, exam_id, subject, topic_name, subtopics, difficulty, priority, estimated_hours, prerequisite_ids, template_ids)
values
('t1', 'exam-ssc-cgl', 'Quantitative Aptitude', 'Percentage', '["Percentage meaning","Increase and decrease","Part-whole comparison"]', 2, 'HIGH', 3.0, '[]', '[]'),
('t2', 'exam-ssc-cgl', 'Quantitative Aptitude', 'Profit & Loss', '["Cost price","Selling price","Profit percent","Loss percent"]', 3, 'HIGH', 3.5, '[]', '[]'),
('t3', 'exam-ssc-cgl', 'Quantitative Aptitude', 'Time & Work', '["Work rate","Combined work","Efficiency"]', 3, 'HIGH', 3.0, '[]', '[]'),
('t4', 'exam-ssc-cgl', 'Quantitative Aptitude', 'Ratio & Proportion', '["Equivalent ratios","Proportion","Cross multiplication"]', 2, 'MED', 2.5, '[]', '[]'),
('t5', 'exam-ssc-cgl', 'Logical Reasoning', 'Puzzles', '["Clue ordering","Tables","Elimination"]', 4, 'HIGH', 4.0, '[]', '[]'),
('t6', 'exam-ssc-cgl', 'Logical Reasoning', 'Seating Arrangement', '["Linear seating","Circular seating","Left-right direction"]', 4, 'HIGH', 3.5, '[]', '[]'),
('t7', 'exam-ssc-cgl', 'Logical Reasoning', 'Coding-Decoding', '["Alphabet shifts","Position values","Pattern checking"]', 3, 'MED', 2.5, '[]', '[]'),
('t8', 'exam-ssc-cgl', 'Logical Reasoning', 'Direction Sense', '["North reference","Movement drawing","Distance check"]', 2, 'MED', 2.0, '[]', '[]'),
('sbi-t1', 'exam-sbi-po', 'Quantitative Aptitude', 'Data Interpretation', '["Units","Tables","Percent change","Averages"]', 4, 'HIGH', 5.0, '[]', '[]'),
('sbi-t2', 'exam-sbi-po', 'Quantitative Aptitude', 'Number Series', '["Differences","Ratios","Squares","Alternating patterns"]', 3, 'HIGH', 3.0, '[]', '[]'),
('sbi-t3', 'exam-sbi-po', 'Quantitative Aptitude', 'Simplification', '["BODMAS","Fractions","Approximation"]', 2, 'HIGH', 2.5, '[]', '[]'),
('sbi-t5', 'exam-sbi-po', 'Logical Reasoning', 'Puzzles', '["Clue ordering","Tables","Elimination"]', 5, 'HIGH', 5.0, '[]', '[]'),
('sbi-t6', 'exam-sbi-po', 'Logical Reasoning', 'Syllogisms', '["Statements","Conclusions","Venn diagrams"]', 3, 'MED', 2.5, '[]', '[]'),
('sbi-t7', 'exam-sbi-po', 'Logical Reasoning', 'Input-Output', '["Step comparison","Sorting rules","Position changes"]', 4, 'MED', 3.0, '[]', '[]'),
('ibps-t1', 'exam-ibps-po', 'Quantitative Aptitude', 'Percentage', '["Percentage meaning","Increase and decrease","Part-whole comparison"]', 2, 'HIGH', 3.0, '[]', '[]'),
('ibps-t2', 'exam-ibps-po', 'Quantitative Aptitude', 'Simplification', '["BODMAS","Fractions","Approximation"]', 2, 'HIGH', 2.5, '[]', '[]'),
('ibps-t3', 'exam-ibps-po', 'Quantitative Aptitude', 'Time & Work', '["Work rate","Combined work","Efficiency"]', 3, 'HIGH', 3.0, '[]', '[]'),
('ibps-t4', 'exam-ibps-po', 'Quantitative Aptitude', 'Data Interpretation', '["Units","Tables","Percent change","Averages"]', 4, 'HIGH', 4.5, '[]', '[]'),
('ibps-t5', 'exam-ibps-po', 'Logical Reasoning', 'Puzzles', '["Clue ordering","Tables","Elimination"]', 4, 'HIGH', 4.0, '[]', '[]'),
('ibps-t6', 'exam-ibps-po', 'Logical Reasoning', 'Syllogisms', '["Statements","Conclusions","Venn diagrams"]', 3, 'MED', 2.5, '[]', '[]')
on conflict (id) do update set
    exam_id = excluded.exam_id,
    subject = excluded.subject,
    topic_name = excluded.topic_name,
    subtopics = excluded.subtopics,
    difficulty = excluded.difficulty,
    priority = excluded.priority,
    estimated_hours = excluded.estimated_hours,
    prerequisite_ids = excluded.prerequisite_ids,
    template_ids = excluded.template_ids;

insert into topic_lesson_material
(id, topic_id, simple_explanation, concept_points, worked_example, common_mistakes, quick_trick, practice_prompt, recap, is_active)
select
    'lesson-' || id,
    id,
    topic_name || ' becomes easier when you first write what is given, then choose the rule, then check the answer.',
    jsonb_build_array(
        'Read the question slowly and mark the known values.',
        'Choose one reliable method before calculating.',
        'Check the final answer with the options before moving on.'
    ),
    case
        when topic_name = 'Percentage' then 'If 30% of a value is 90, the full value is 90 x 100 / 30 = 300.'
        when topic_name = 'Profit & Loss' then 'If cost price is 800 and selling price is 920, profit is 120 and profit percent is 120 / 800 x 100 = 15%.'
        when topic_name = 'Time & Work' then 'If A finishes work in 10 days, A does 1/10 work per day. Add rates when people work together.'
        else 'Create a small table or equation, fill it step by step, and verify the answer before choosing.'
    end,
    jsonb_build_array(
        'Skipping the base value or direction.',
        'Calculating before organizing the data.',
        'Selecting an option without checking the result.'
    ),
    'Turn the statement into a small table or equation first.',
    'Try one short question: write the given values, choose the rule, solve, and check your answer.',
    'Remember the setup, apply the rule carefully, and verify before choosing an option.',
    true
from syllabus_topics
on conflict (id) do update set
    simple_explanation = excluded.simple_explanation,
    concept_points = excluded.concept_points,
    worked_example = excluded.worked_example,
    common_mistakes = excluded.common_mistakes,
    quick_trick = excluded.quick_trick,
    practice_prompt = excluded.practice_prompt,
    recap = excluded.recap,
    is_active = excluded.is_active;

insert into quiz_templates
(id, topic_id, template_type, difficulty, template_body, answer_key, is_active)
select
    'quiz-' || id || '-1',
    id,
    'mcq',
    difficulty,
    jsonb_build_object(
        'question_text', 'What is the best first step for ' || topic_name || '?',
        'options', jsonb_build_array('Guess quickly', 'Organize the given data', 'Ignore units', 'Skip the topic')
    ),
    jsonb_build_object('correct_index', 1, 'explanation', 'Organizing the given data makes the method clear and reduces mistakes.'),
    true
from syllabus_topics
on conflict (id) do update set
    template_body = excluded.template_body,
    answer_key = excluded.answer_key,
    difficulty = excluded.difficulty,
    is_active = excluded.is_active;

insert into quiz_templates
(id, topic_id, template_type, difficulty, template_body, answer_key, is_active)
select
    'quiz-' || id || '-2',
    id,
    'mcq',
    difficulty,
    jsonb_build_object(
        'question_text', 'Why should you check the final answer in ' || topic_name || '?',
        'options', jsonb_build_array('To avoid base or direction errors', 'To make it slower', 'To skip formulas', 'To remove practice')
    ),
    jsonb_build_object('correct_index', 0, 'explanation', 'Checking catches common mistakes before you lock the option.'),
    true
from syllabus_topics
on conflict (id) do update set
    template_body = excluded.template_body,
    answer_key = excluded.answer_key,
    difficulty = excluded.difficulty,
    is_active = excluded.is_active;

insert into quiz_templates
(id, topic_id, template_type, difficulty, template_body, answer_key, is_active)
select
    'quiz-' || id || '-3',
    id,
    'mcq',
    difficulty,
    jsonb_build_object(
        'question_text', 'What should you revise after a weak score in ' || topic_name || '?',
        'options', jsonb_build_array('Only unrelated topics', 'The same weak concept', 'Nothing', 'Only easy questions')
    ),
    jsonb_build_object('correct_index', 1, 'explanation', 'Weak concepts improve fastest with targeted revision and another attempt.'),
    true
from syllabus_topics
on conflict (id) do update set
    template_body = excluded.template_body,
    answer_key = excluded.answer_key,
    difficulty = excluded.difficulty,
    is_active = excluded.is_active;

insert into quiz_templates
(id, topic_id, template_type, difficulty, template_body, answer_key, is_active)
values
('quiz-t1-4', 't1', 'mcq', 2, '{"question_text":"What is 25% of 240?","options":["40","50","60","80"]}', '{"correct_index":2,"explanation":"25% is one-fourth; 240 / 4 = 60."}', true),
('quiz-t1-5', 't1', 'mcq', 2, '{"question_text":"A number increases from 80 to 100. What is the percentage increase?","options":["20%","25%","30%","40%"]}', '{"correct_index":1,"explanation":"Increase is 20 on original 80, so 20 / 80 x 100 = 25%."}', true),
('quiz-t2-4', 't2', 'mcq', 3, '{"question_text":"Cost price is 500 and selling price is 650. What is the profit percent?","options":["20%","25%","30%","35%"]}', '{"correct_index":2,"explanation":"Profit is 150; 150 / 500 x 100 = 30%."}', true),
('quiz-t2-5', 't2', 'mcq', 3, '{"question_text":"Loss percent is calculated on which value?","options":["Selling price","Marked price","Cost price","Discount"]}', '{"correct_index":2,"explanation":"Profit and loss percentages are calculated on cost price."}', true)
on conflict (id) do update set
    template_body = excluded.template_body,
    answer_key = excluded.answer_key,
    difficulty = excluded.difficulty,
    is_active = excluded.is_active;
