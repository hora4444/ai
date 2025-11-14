-- [II] SELECT문 - 조회

-- 1. SELECT 문장 작성법
SELECT * FROM TAB; -- 현 계정(scott)이 가지고 있는 테이블 정보(실행: CTRL+ENTER),[-- 가 SQL 주석]
SELECT * FROM DEPT; -- DEPT 테이블의 모든 열, 모든 행
SELECT * FROM SALGRADE; -- SALGRADE 테이블의 모든 열, 모든 행
SELECT * FROM EMP; -- EMP 테이블의 모든 열, 모든 행

-- 2. 특정 열만 출력
DESC EMP;
    -- EMP 테이블의 구조 (주석과 같은 줄에 있다면 실행되지 않을 수 있음)
SELECT EMPNO, ENAME, SAL, JOB FROM EMP; -- EMP 테이블의 SELECT절에 지정된 열만 출력
SELECT EMPNO AS "사 번", ENAME AS "이 름", SAL AS "급 여", JOB AS "직 책" FROM EMP; -- 열 이름에 별칭을 두는경우 EX. 열이름 AS 별칭
SELECT EMPNO "사 번", ENAME "이 름", SAL "급 여", JOB FROM EMP; -- AS를 쓰지 않더라도 별칭으로 둘 수 있다
SELECT EMPNO 사번, ENAME 이름, SAL 급여, JOB FROM EMP; -- 만약 별칭에 SPACE가 없다면 따옴표도 생략 가능

-- 3. 특정 행 출력 : WHERE 절(조건절) -- 비교연산자 :  >, >= , <, <=, 다르다(!=, ^=, <>), =(같다)
SELECT EMPNO 사번, ENAME 이름, SAL 급여 FROM EMP WHERE SAL = 3000;
SELECT EMPNO NO, ENAME NAME, SAL FROM EMP WHERE SAL != 3000;
SELECT EMPNO NO, ENAME NAME, SAL FROM EMP WHERE SAL ^= 3000;
SELECT EMPNO NO, ENAME NAME, SAL FROM EMP WHERE SAL <> 3000;
    -- 비교연산자는 숫자, 문자, 날짜형 모두 가능
    -- EX1. 사원 이름이 'A','B','C'로 시작하는 사우너의 모든 열(필드)
    -- A < AA < AAA < AAAA ..... < B < BA < .... < C < CA < ....
    SELECT * FROM EMP WHERE ENAME < 'D';
    -- EX2. 81년도 이전에 입사한 사원의 모든 열(필드)
    SELECT * FROM EMP WHERE HIREDATE <= '81/01/01';
    -- EX3. 부서번호(DEPTNO)가 10번인 사원의 모든 필드
    SELECT * FROM EMP WHERE DEPTNO = 10;
    -- SQL문은 대소문자 구별없음, 데이터는 대소문자 구별
    -- EX4. 이름이(ENAME)이 SCOTT인 직원의 모든 데이터(필드)
    SELECT * FROM EMP where ename = 'SCOTT';

-- 4. WHERE(조건절) -- 논리연산자 : AND, OR, NOT
    --EX1. 급여(SAL)가 2000이상 3000이하인 직원의 모든 필드
    SELECT * FROM EMP WHERE  SAL >=2000 AND SAL<=3000;
    -- EX2. 82년도 입사한 사원의 모든 필드
    SELECT * FROM EMP WHERE HIREDATE >= '82/01/01' AND HIREDATE <= '82/12/31';
   
    --날짜 표기법 셋팅 (현재: RR/MM/DD)
    ALTER SESSION SET NLS_DATE_FORMAT = "RR-MM-DD";
    SELECT * FROM EMP;
    SELECT * FROM EMP 
        WHERE TO_CHAR(HIREDATE, 'YYYY-MM-DD') >= '1982-01-01' AND TO_CHAR(HIREDATE,'YYYY-MM-DD') <= '1982-12-31';
    -- EX3. 부서번호가 10이 아닌 직원의 모든 필드
    SELECT * FROM EMP WHERE DEPTNO != 10;
    SELECT * FROM EMP WHERE NOT DEPTNO = 10;
    
-- 5. 산술연산자 (SELECT절, WHERE절, ORDER BY절)
SELECT EMPNO, ENAME, SAL "인상 전 월급",SAL*1.1 "인상 후 월급" FROM EMP;
    -- EX.1 연봉이 10,000 이상인 직원의 ENAME(이름),SAL(월급), 연봉(SAL*12)
    SELECT ENAME 이름, SAL 월급, SAL*12 연봉 --(3)
        FROM EMP               --(1)
        WHERE SAL*12 >= 10000  --(2)   -- WHERE절에는 별칭 사용 불가
        ORDER BY 연봉 DESC;    --(4)
    -- 산술연산의 결과는 NULL을 포함하면 결과도 NULL
    -- NVL(NULL일수도 있는 필드명, 대체값)을 이용 : 필드명과 대체값은 타입이 일치
    -- EX.2 연봉이 20,000 이상인 직원의 이름, 월급, 상여(COMM), 연봉(SAL*12 + COMM) 출력
    SELECT ENAME 이름, SAL 월급, NVL(COMM,0) 상여, SAL*12+ NVL(COMM,0) 연봉 FROM EMP WHERE SAL*12+ NVL(COMM,0)>= 20000 ORDER BY 연봉;
    -- EX3. 모든 사원의 ENAME, MGR(상사사번)을 출력-상사사번이 없으면 'CEO'
    SELECT ENAME,NVL(TO_CHAR(MGR),'CEO') FROM EMP;

-- 6. 연결연산자 (||) : 필드내용이나 문자를 연결
SELECT ENAME || '=' || JOB FROM EMP;

-- 7. 중복제거(DISTINCT)
SELECT DISTINCT JOB FROM EMP;
SELECT DISTINCT DEPTNO FROM EMP;

-- 연습문제

--1. emp 테이블의 구조 출력
DESC EMP;
--2. emp 테이블의 모든 내용을 출력 
SELECT * FROM EMP;
--3. 현 scott 계정에서 사용가능한 테이블 출력
SELECT * FROM TAB;
--4. emp 테이블에서 사번(EMPNO), 이름(ENAME), 급여(SAL), 업무(JOB), 입사일(HIREDATE) 출력
SELECT EMPNO 사번, ENAME 이름, SAL 급여, JOB 업무, HIREDATE 입사일 FROM EMP;
--5. emp 테이블에서 급여가 2000미만인 사람의 사번, 이름, 급여 출력
SELECT EMPNO 사번, ENAME 이름, SAL 급여 FROM EMP  WHERE SAL <2000;
--6. 입사일이 81/02이후에 입사한 사람의 사번, 이름, 업무, 입사일 출력
SELECT EMPNO 사번, ENAME 이름, JOB 업무, HIREDATE 입사일 FROM EMP WHERE TO_CHAR(HIREDATE, 'YYYY-MM-DD') >= '1981-02-01';
-- 날짜형태로는 TO_DATE()
SELECT EMPNO 사번, ENAME 이름, JOB 업무, HIREDATE 입사일 FROM EMP WHERE HIREDAT >= TO_DATE('81-02-01','RR-MM-DD');
--7. 업무가 SALESMAN인 사람들 모든 자료 출력
SELECT * FROM EMP WHERE JOB = 'SALESMAN'; 
--8. 업무가 CLERK이 아닌 사람들 모든 자료 출력
SELECT * FROM EMP WHERE JOB != 'CLERK';
--9. 급여가 1500이상이고 3000이하인 사람의 사번, 이름, 급여 출력
SELECT EMPNO 사번, ENAME 이름, SAL 급여 FROM EMP WHERE SAL >=1500 AND SAL <=3000;
--10. 부서코드(DEPTNO)가 10번이거나 30인 사람의 사번, 이름, 업무, 부서코드 출력
SELECT EMPNO 사번, ENAME 이름, JOB 업무, DEPTNO 부서코드 FROM EMP WHERE DEPTNO = 10 OR DEPTNO = 30;
--11. 업무가 SALESMAN이거나 급여가 3000이상인 사람의 사번, 이름, 업무, 부서코드 출력
SELECT EMPNO 사번, ENAME 이름, JOB 업무,  DEPTNO 부서코드 FROM EMP WHERE JOB = 'SALESMAN' OR SAL >= 3000; 
--12. 급여가 2500이상이고 업무가 MANAGER인 사람의 사번, 이름, 업무, 급여 출력
SELECT EMPNO 사번, ENAME 이름, JOB 업무, SAL 급여 FROM EMP WHERE SAL >= 2500 AND JOB = 'MANAGER';
--13.“ename은 XXX 업무이고 연봉은 XX다” 스타일로 모두 출력(연봉은 SAL*12+COMM)
SELECT ENAME || '은 ' || JOB || ' 업무이고 연봉은 ' || (SAL*12+NVL(COMM,0)) || '다' MSG FROM EMP; -- ||의 우선순위가 매우 높아 문자열과 SAL이 먼저 계산되어 괄호가 없다면 오류가 발생한다.

-- 8. SQL연산자(BETWEEN, IN, LIKE, IS NULL)
-- (1) BETWEEN A AND B : A 부터 B 까지 (A,B 포함, A<=B)
    -- EX1. SAL 이 1500 이상 3000 이하
    SELECT * FROM EMP WHERE SAL BETWEEN 1500 AND 3000;
    -- EX2. SAL 이 1500 미만 3000 초과
    SELECT * FROM EMP WHERE SAL NOT BETWEEN 1500 AND 3000;
    -- EX2. 81년도 봄(3월~5월)에 입사한 직원의 모든 필드
    SELECT * FROM EMP WHERE HIREDATE BETWEEN TO_DATE('81-03-01','RR-MM-DD') AND TO_DATE('81-05-30','RR-MM-DD');
-- (2) 필드명 IN(값 1, 값 2 ....) : 필드명의 값 들 중 IN안의 값중의 값을 가지는 것들
    -- EX1. 부서코드가 10번이거나 30이거나 40인 사람의 모든 정보
    SELECT * FROM EMP WHERE DEPTNO IN(10,30,40);
    -- EX2. 직책(JOB)이 'MANAGER'이거나 'ANALYST'인 사원의 모든 정보
    SELECT * FROM EMP WHERE JOB IN('MANAGER','ANALYST');
    -- EX1-1. 부서코드가 10번, 30번 40번이 아닌 사람의 모든 정보
    SELECT * FROM EMP WHERE DEPTNO NOT IN(10,30,40);
-- (3) 필드명 LIKE '패턴' :  % = (액세스의 *), _ = (액세스의 ?)
    -- EX1. 이름이 M으로 시작하는 사원의 모든 정보
    SELECT * FROM EMP WHERE ENAME LIKE 'M%';
    -- EX2. 이름이 S으로 끝나는 사원의 모든 정보
    SELECT * FROM EMP WHERE ENAME LIKE '%S';
    -- EX3. 이름에 N이 들어가는 사원의 모든 정보
    SELECT * FROM EMP WHERE ENAME LIKE '%N%';
    -- EX4. 이름에 N이 들어가고 JOB에 S가 들어가는 사원의 모든 정보
    SELECT * FROM EMP WHERE ENAME LIKE '%N%' AND JOB LIKE '%S%';
    -- EX5. SAL이 5로 끝나는 모든 사원의 정보
     SELECT * FROM EMP WHERE SAL LIKE '%5';
    -- EX6. 82년도에 입사한 사원
    SELECT * FROM EMP WHERE HIREDATE LIKE '82/%';
    SELECT * FROM EMP WHERE TO_CHAR(HIREDATE,'RR')=82;
    -- EX7. 1월에 입사한 사원
    SELECT * FROM EMP WHERE HIREDATE LIKE '__/01/__';
    SELECT * FROM EMP WHERE TO_CHAR(HIREDATE,'MM')=01;
    -- EX8. 이름에 %가 들어간 사원
    SELECT * FROM EMP WHERE ENAME LIKE '%\%%' ESCAPE '\'; -- ESCAPE 문자 바로 뒤의 한 글자를 문자로 취급
        -- 이름에 %가 들어간 데이터 INSERT
        INSERT INTO EMP VALUES (9999, '홍보순%', NULL, NULL, NULL, 9000, 9000, 40);
        SELECT * FROM EMP;
        -- 이름에 %가 들어간 데이터 취소
        ROLLBACK; -- DML(데이터 조작어:추가, 수정, 삭제, 검색)을 취소
--(4) 필드명 IS NULL : 필드이 NULL인지 검색할 때
    -- EX1. COMM(상여)이 없는 사원
    SELECT * FROM EMP WHERE COMM IS NULL OR COMM =0;
    -- EX2. 상여금을 받는 사원
    SELECT * FROM EMP WHERE COMM IS NOT NULL AND COMM != 0;

-- 9. 정렬(오름차순, 내림차순): ORDER BY    
SELECT * FROM EMP ORDER BY SAL; -- 오름차순
SELECT * FROM EMP ORDER BY SAL DESC; -- 내림차순
    -- EX1. 급여 내림차순, 급여 같으면 입사일 최신순
    SELECT * FROM EMP ORDER BY SAL DESC, HIREDATE DESC;
    -- EX2. 급여가 2000 초과하는 사원을 이름 오름차순으로 정렬
    SELECT * FROM EMP WHERE SAL > 2000 ORDER BY ENAME;
    
-- <총 연습문제>
--1.	EMP 테이블에서 sal이 3000이상인 사원의 empno, ename, job, sal을 출력
SELECT EMPNO, ENAME, JOB, SAL 
    FROM EMP WHERE SAL >=3000;
--2.	EMP 테이블에서 empno가 7788인 사원의 ename과 deptno를 출력
SELECT ENAME, DEPTNO 
    FROM EMP WHERE EMPNO=7788;
--3.	연봉(SAL*12+COMM)이 24000이상인 사번, 이름, 급여 출력 (급여순정렬)
SELECT EMPNO, ENAME, SAL 
    FROM EMP WHERE (SAL*12+NVL(COMM,0))>=24000 ORDER BY SAL;
--4.	입사일이 1981년 2월 20과 1981년 5월 1일 사이에 입사한 사원의 사원명, 직책, 입사일을 출력 (단 hiredate 순으로 출력)
SELECT ENAME, JOB, HIREDATE
    FROM EMP WHERE TO_CHAR(HIREDATE,'RR/MM/DD') BETWEEN '81/02/20' AND '81/05/01' 
    ORDER BY HIREDATE;
--5.	deptno가 10,20인 사원의 모든 정보를 출력 (단 ename순으로 정렬)
SELECT *
    FROM EMP WHERE DEPTNO IN (10,20) 
    ORDER BY ENAME;
--6.	sal이 1500이상이고 deptno가 10,30인 사원의 ename과 sal를 출력
-- (단 출력되는 결과의 타이틀을 employee과 Monthly Salary로 출력)
SELECT ENAME employee, SAL "Monthly salary"
    FROM EMP WHERE SAL>=1500 AND DEPTNO IN(10,30);
--7.	hiredate가 1982년인 사원의 모든 정보를 출력
SELECT *
    FROM EMP WHERE TO_CHAR(HIREDATE,'RR')='82';
--8.	이름의 첫자가 C부터  P로 시작하는 사람의 이름, 급여 이름순 정렬
SELECT ENAME, SAL
    FROM EMP WHERE ENAME BETWEEN 'C' AND 'Q' AND ENAME != 'Q'
    ORDER BY ENAME;
--9.	comm이 sal보다 10%가 많은 모든 사원에 대하여 이름, 급여, 상여금을 
--출력하는 SELECT 문을 작성
SELECT ENAME, JOB, COMM
    FROM EMP WHERE NVL(COMM,0) >= SAL*1.1; -- COMM이 NULL일 경우 연산 시 자동으로 False 
--10.	job이 CLERK이거나 ANALYST이고 sal이 1000,3000,5000이 아닌 모든 사원의 정보를 출력
SELECT *
    FROM EMP WHERE JOB IN ('CLERK', 'ANALYST') AND SAL NOT IN (1000,3000,5000);
--11.	ename에 L이 두 자가 있고 deptno가 30이거나 또는 mgr이 7782인 사원의 
--모든 정보를 출력하는 SELECT 문을 작성하여라.
SELECT *
    FROM EMP WHERE ENAME LIKE '%L%L%' AND DEPTNO = 30 OR MGR =7782;
--12.	입사일이 81년도인 직원의 사번, 사원명, 입사일, 업무, 급여를 출력
SELECT EMPNO, ENAME, HIREDATE, JOB, SAL
    FROM EMP WHERE TO_CHAR(HIREDATE,'RR')='81';
--13.	입사일이81년이고 업무가 'SALESMAN'이 아닌 직원의 사번, 사원명, 입사일, 
-- 업무, 급여를 검색하시오.
SELECT EMPNO, ENAME, HIREDATE, JOB, SAL
    FROM EMP WHERE TO_CHAR(HIREDATE,'RR')='81' AND JOB != 'SALESMAN';
--14.	사번, 사원명, 입사일, 업무, 급여를 급여가 높은 순으로 정렬하고, 
-- 급여가 같으면 입사일이 빠른 사원으로 정렬하시오.
SELECT EMPNO, ENAME, HIREDATE, JOB, SAL
    FROM EMP
    ORDER BY SAL DESC, HIREDATE ASC;
--15.	사원명의 세 번째 알파벳이 'N'인 사원의 사번, 사원명을 검색하시오
SELECT EMPNO, ENAME
    FROM EMP WHERE ENAME LIKE '__N%';
--16.	사원명에 'A'가 들어간 사원의 사번, 사원명을 출력
SELECT EMPNO, ENAME
    FROM EMP WHERE ENAME LIKE '%A%';
--17.	연봉(SAL*12)이 35000 이상인 사번, 사원명, 연봉을 검색 하시오.
SELECT EMPNO, ENAME, SAL*12 ANNUALSAL
    FROM EMP WHERE SAL*12 >= 35000;
