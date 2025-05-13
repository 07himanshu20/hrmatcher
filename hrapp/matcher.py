def match_resume(resume_data, job):
    score = 0
    if resume_data['experience'] >= job.experience_required:
        score += 20

    if job.education_required.lower() in resume_data['education'].lower():
        score += 20

    job_skills = [skill.strip().lower() for skill in job.skills_required.split(',')]
    matched_skills = set(job_skills) & set(resume_data['skills'])
    score += len(matched_skills) * 10

    return score
