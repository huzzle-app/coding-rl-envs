# frozen_string_literal: true

module Api
  module V1
    class ProjectsController < ApplicationController
      before_action :set_organization, only: [:index, :create]
      before_action :set_project, only: [:show, :update, :destroy]

      def index
        @projects = policy_scope(@organization.projects)
                    .includes(:creator, :milestones)

        
        @projects = @projects.order(params[:sort] || 'created_at DESC')

        render json: @projects
      end

      def show
        authorize @project

        render json: ProjectSerializer.new(@project, include: [:milestones, :members])
      end

      def create
        @project = @organization.projects.build(project_params)
        @project.creator = current_user

        authorize @project

        if @project.save
          # Add creator as project member
          @project.project_memberships.create!(user: current_user, role: 'admin')

          render json: @project, status: :created
        else
          render json: { errors: @project.errors }, status: :unprocessable_entity
        end
      end

      def update
        authorize @project

        if @project.update(project_params)
          render json: @project
        else
          render json: { errors: @project.errors }, status: :unprocessable_entity
        end
      end

      def destroy
        authorize @project

        
        # This can timeout for projects with many tasks
        @project.destroy

        head :no_content
      end

      private

      def set_organization
        @organization = Organization.friendly.find(params[:organization_id])
        authorize @organization, :show?
      end

      def set_project
        @project = Project.friendly.find(params[:id])
      end

      def project_params
        params.require(:project).permit(
          :name, :description, :status, :due_date,
          :visibility, :organization_id
        )
      end
    end
  end
end
